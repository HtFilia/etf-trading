from __future__ import annotations
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional


@dataclass
class AppConfig:
    # General
    env_loaded: bool
    dev_mode: bool
    tick_interval_ms: float

    # ZMQ & IPC
    zmq_dir: str
    md_sock: str
    fx_sock: str
    pcf_sock: str
    pricing_sock: str

    # WS gateway
    ws_host: str
    ws_port: int

    # Logging
    log_level: str
    log_format: str
    log_color: bool
    log_timezone_utc: bool
    log_file: Optional[str]
    log_file_max_bytes: int
    log_file_backup: int
    log_include_pid: bool

    @property
    def tick_interval(self) -> float:
        return self.tick_interval_ms / 1000.0

    @property
    def md_ipc(self) -> str:
        return self._make_ipc(self.md_sock)
    
    @property
    def fx_ipc(self) -> str:
        return self._make_ipc(self.fx_sock)

    @property
    def pcf_ipc(self) -> str:
        return self._make_ipc(self.pcf_sock)

    @property
    def pricing_ipc(self) -> str:
        return self._make_ipc(self.pricing_sock)
    
    def _make_ipc(self, sock: str) -> str:
        if sock.startswith(('ipc://', 'tcp://')):
            return sock
        if sock.startswith('/'):
            return f'ipc://{sock}'
        return f'ipc://{Path(self.zmq_dir) / sock}'


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    try:
        from dotenv import load_dotenv
        loaded = load_dotenv(override=True)
    except:
        loaded = False

    def as_bool(s: Optional[str], default: bool) -> bool:
        if s is None:
            return default
        return s.strip().lower() in ('1', 'true', 'yes', 'on')

    def as_float(s: Optional[str], default: float) -> float:
        try:
            return float(s) if s is not None else default
        except ValueError:
            return default

    def as_int(s: Optional[str], default: int) -> int:
        try:
            return int(s) if s is not None else default
        except ValueError:
            return default

    return AppConfig(
        # General
        env_loaded=loaded,
        dev_mode=as_bool(os.environ.get('DEV_MODE'), True),
        tick_interval_ms=as_float(os.environ.get('TICK_INTERVAL_MS'), 1000.0),
        # ZMQ & IPC
        zmq_dir=os.environ.get('ZMQ_DIR', '/tmp/etf-trading'),
        md_sock=os.environ.get('MARKET_DATA_SOCK', 'md.sock'),
        fx_sock=os.environ.get('FX_SOCK', 'fx.sock'),
        pcf_sock=os.environ.get('PCF_SOCK', 'pcf.sock'),
        pricing_sock=os.environ.get('PRICING_SOCK', 'pricing.sock'),
        # WS gateway
        ws_host=os.environ.get('WS_HOST', 'localhost'),
        ws_port=as_int(os.environ.get('WS_PORT'), 9080),
        # Logging
        log_level=os.environ.get('LOG_LEVEL', 'INFO'),
        log_format=os.environ.get('LOG_FORMAT', 'json'),
        log_color=as_bool(os.environ.get('LOG_COLOR'), True),
        log_timezone_utc=os.environ.get('LOG_TIMEZONE', 'UTC').upper() == 'UTC',
        log_file=os.environ.get('LOG_FILE'),
        log_file_max_bytes=as_int(os.environ.get('LOG_FILE_MAX_BYTES'), 10 * 1024 * 1024),
        log_file_backup=as_int(os.environ.get('LOG_FILE_BACKUP'), 5),
        log_include_pid=as_bool(os.environ.get('LOG_INCLUDE_PID'), True),
    )
