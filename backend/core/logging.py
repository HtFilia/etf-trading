from __future__ import annotations
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from logging import Handler, LogRecord, Formatter
from logging.handlers import RotatingFileHandler
from typing import Any, Optional, Dict
import contextvars
from backend.core.config import get_config

_request_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('request_id', default=None)
_session_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('session_id', default=None)
_service_name_for_records: Optional[str] = None
_original_factory = logging.getLogRecordFactory()


def set_request_id(value: Optional[str] = None) -> str:
    rid = value or uuid.uuid4().hex
    _request_id.set(rid)
    return rid


def get_request_id() -> Optional[str]:
    return _request_id.get()


def set_session_id(value: Optional[str] = None) -> str:
    sid = value or uuid.uuid4().hex
    _session_id.set(sid)
    return sid


def get_session_id() -> Optional[str]:
    return _session_id.get()


def _service_record_factory(*args, **kwargs):
    record = _original_factory(*args, **kwargs)
    if _service_name_for_records and record.name == '__main__':
        record.name = _service_name_for_records
    return record


class JsonFormatter(Formatter):
    def __init__(self, service: str):
        super().__init__()
        self._cfg = get_config()
        self.service = service

    def format(self, record: LogRecord) -> str:
        ts = datetime.fromtimestamp(
            record.created,
            tz=timezone.utc if self._cfg.log_timezone_utc else None,
        )
        payload: Dict[str, Any] = {
            'ts': ts.isoformat(),
            'level': record.levelname,
            'service': self.service,
            'logger': record.name,
            'msg': record.getMessage(),
            'module': record.module,
            'func': record.funcName,
            'line': record.lineno,
        }
        if self._cfg.log_include_pid:
            payload['pid'] = os.getpid()
        rid, sid = get_request_id(), get_session_id()
        if rid:
            payload['request_id'] = rid
        if sid:
            payload['session_id'] = sid

        for k in ('topic', 'security_id', 'share_class_id', 'event', 'count'):
            if hasattr(record, k):
                payload[k] = getattr(record, k)

        if record.exc_info:
            payload['exc'] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


class TextFormatter(Formatter):
    _COLORS = {
        'DEBUG': '\x1b[38;5;245m',
        'INFO': '\x1b[38;5;39m',
        'WARNING': '\x1b[33m',
        'ERROR': '\x1b[31m',
        'CRITICAL': '\x1b[41;97m',
    }
    _RESET = '\x1b[0m'

    def __init__(self, service: str):
        self._cfg = get_config()
        self.service = service
        self._color_enabled = self._cfg.log_color and sys.stderr.isatty()

    def format(self, record: LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc if self._cfg.log_timezone_utc else None)
        level = record.levelname
        lvl = f'{self._COLORS[level]}{level}{self._RESET}' if self._color_enabled else level
        pid = f' pid={os.getpid()}' if self._cfg.log_include_pid else ''
        rid, sid = get_request_id(), get_session_id()
        ctx = ''
        if rid:
            ctx += f' {rid=}'
        if sid:
            ctx += f' {sid=}'
        base = f'{ts.isoformat()} | {self.service} | {lvl} | {record.name}{pid}{ctx} | {record.getMessage()}'
        if record.exc_info:
            base += '\n' + self.formatException(record.exc_info)
        return base


def _make_stream_handler(service: str) -> Handler:
    cfg = get_config()
    h = logging.StreamHandler(stream=sys.stdout)
    if cfg.log_format.lower() == 'json':
        h.setFormatter(JsonFormatter(service))
    else:
        h.setFormatter(TextFormatter(service))
    return h


def _make_file_handler(service: str) -> Optional[Handler]:
    cfg = get_config()
    if not cfg.log_file:
        return None
    fh: Handler = RotatingFileHandler(cfg.log_file, maxBytes=cfg.log_file_max_bytes, backupCount=cfg.log_file_backup)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(JsonFormatter(service))
    return fh


_initialized = False


def init_logging(service: str) -> None:
    global _initialized, _service_name_for_records
    if _initialized:
        return
    cfg = get_config()

    _service_name_for_records = service
    logging.setLogRecordFactory(_service_record_factory)

    root = logging.getLogger()
    root.setLevel(getattr(logging, cfg.log_level.upper(), logging.INFO))
    root.handlers.clear()
    stream_h = _make_stream_handler(service)
    root.addHandler(stream_h)
    file_h = _make_file_handler(service)
    if file_h:
        root.addHandler(file_h)

    logging.getLogger('asyncio').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('websockets').setLevel(logging.WARNING)

    _initialized = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def integrate_uvicorn(name: str) -> None:
    cfg = get_config()
    handler = _make_stream_handler(name)
    file_handler = _make_file_handler(name)
    for lname in ('uvicorn', 'uvicorn.error', 'uvicorn.access', 'starlette'):
        lg = logging.getLogger(lname)
        lg.handlers.clear()
        lg.propagate = True
        lg.setLevel(getattr(logging, cfg.log_level.upper(), logging.INFO))
        if lname == 'uvicorn.access':
            lg.setLevel(logging.INFO)
        lg.addHandler(handler)
        if file_handler:
            lg.addHandler(file_handler)
