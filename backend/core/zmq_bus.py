from __future__ import annotations

from dataclasses import is_dataclass, asdict
import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Iterable, Optional, Mapping, Sequence

import zmq
import zmq.asyncio

try:
    import numpy as np
except:
    np = None

try:
    import msgpack
except:
    msgpack = None

log = logging.getLogger(__name__)

_CTX = zmq.asyncio.Context.instance()

def _to_plain(obj):
    try:
        from pydantic import BaseModel
        if isinstance(obj, BaseModel):
            return obj.model_dump()
    except:
        pass
    
    if is_dataclass(obj):
        return _to_plain(asdict(obj))
    
    if np is not None:
        if isinstance(obj, (np.generic,)):
            return obj.item()
        if isinstance(obj, np.ndarray):
            return obj.tolist()
    
    if isinstance(obj, Mapping):
        return {k: _to_plain(v) for k, v in obj.items()}
    
    if isinstance(obj, (list, tuple, set)):
        return [_to_plain(v) for v in obj]
    
    return obj
    
def _pack(obj: Dict[str, Any]) -> bytes:
    obj = _to_plain(obj)
    if msgpack:
        return msgpack.packb(obj, use_bin_type=True)
    return json.dumps(obj, separators=(',', ':')).encode('utf-8')

def _unpack(buf: bytes) -> Dict[str, Any]:
    if msgpack:
        return msgpack.unpackb(buf, raw=False)
    return json.loads(buf.decode('utf-8'))

def _now_ms() -> int:
    return int(time.time() * 1000)

def _envelope(topic: str, payload: Dict[str, Any], version: int = 1, ts_ms: Optional[int] = None) -> Dict[str, Any]:
    if ts_ms is None:
        ts_ms = _now_ms()
    return {'type': topic, 'ts': ts_ms, 'v': version, 'payload': payload}

def _zmq_dir() -> Path:
    base = os.environ.get('ZMQ_DIR', '/tmp/etf-trading')
    p = Path(base)
    p.mkdir(parents=True, exist_ok=True)
    return p

def _to_ipc(addr_or_path: str) -> str:
    if addr_or_path.startswith('ipc://'):
        return addr_or_path
    if addr_or_path.startswith('/'):
        return f'ipc://{addr_or_path}'
    return f'ipc://{_zmq_dir() / addr_or_path}'

def _ensure_parent(endpoint_ipc: str) -> Optional[Path]:
    if not endpoint_ipc.startswith('ipc://'):
        return None
    fs_path = Path(endpoint_ipc.replace('ipc://', ''))
    fs_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if fs_path.exists():
            fs_path.unlink()
    except Exception as e:
        log.warning('Could not unlink stale IPC path %s: %s', fs_path, e)
    return fs_path

class PubSocket:
    def __init__(self, sock: zmq.asyncio.Socket, endpoint: str):
        self._sock = sock
        self.endpoint = endpoint
    
    @classmethod
    async def bind(cls, addr_or_path: str) -> 'PubSocket':
        endpoint = _to_ipc(addr_or_path)
        _ensure_parent(endpoint)
        s = _CTX.socket(zmq.PUB)
        s.setsockopt(zmq.LINGER, 0)
        s.bind(endpoint)
        log.info('PUB bound: %s', endpoint)
        return cls(s, endpoint)
    
    async def send(self, topic: str, payload: Dict[str, Any], version: int = 1) -> None:
        env = _envelope(topic=topic, payload=_to_plain(payload), version=version)
        await self._sock.send_multipart([topic.encode('utf-8'), _pack(env)])
    
    async def close(self) -> None:
        try:
            self._sock.close(0)
        except:
            pass

class SubSocket(AsyncIterator[Dict[str, Any]]):
    def __init__(self, sock: zmq.asyncio.Socket, endpoint: str, topics: Iterable[str]):
        self._sock = sock
        self.endpoint = endpoint
        self._topics = list(topics) if topics else ['']
    
    @classmethod
    async def connect(cls, addr_or_path: str, topics: Optional[Iterable[str]] = None) -> 'SubSocket':
        endpoint = _to_ipc(addr_or_path)
        s = _CTX.socket(zmq.SUB)
        s.setsockopt(zmq.LINGER, 0)
        s.connect(endpoint)
        tlist = list(topics) if topics else ['']
        for t in tlist:
            s.setsockopt_string(zmq.SUBSCRIBE, t)
        log.info('SUB connected: %s (topics=%s)', endpoint, tlist)
        return cls(s, endpoint, tlist)
    
    async def recv(self) -> Dict[str, Any]:
        topic_b, payload_b = await self._sock.recv_multipart()
        topic = topic_b.decode('utf-8')
        env = _unpack(payload_b)
        env.setdefault('type', topic)
        return env
    
    def __aiter__(self) -> 'SubSocket':
        return self
    
    async def __anext__(self) -> Dict[str, Any]:
        try:
            return await self.recv()
        except (asyncio.CancelledError, zmq.error.ContextTerminated):
            raise StopAsyncIteration
    
    async def close(self) -> None:
        try:
            self._sock.close(0)
        except:
            pass

class ReqSocket:
    def __init__(self, sock: zmq.asyncio.Socket, endpoint: str):
        self._sock = sock
        self.endpoint = endpoint
        self._lock = asyncio.Lock()
    
    @classmethod
    async def connect(cls, addr_or_path: str) -> 'ReqSocket':
        endpoint = _to_ipc(addr_or_path)
        s = _CTX.socket(zmq.REQ)
        s.setsockopt(zmq.LINGER, 0)
        s.connect(endpoint)
        log.info('REQ connected: %s', endpoint)
        return cls(s, endpoint)
    
    async def send_and_recv(
        self,
        payload: Dict[str, Any],
        *,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        async with self._lock:
            await self._sock.send(_pack(payload))
            if timeout:
                buf = await asyncio.wait_for(self._sock.recv(), timeout=timeout)
            else:
                buf = await self._sock.recv()
            return _unpack(buf)
    
    async def close(self) -> None:
        try:
            self._sock.close(0)
        except:
            pass

class RepSocket:
    def __init__(self, sock: zmq.asyncio.Socket, endpoint: str):
        self._sock = sock
        self.endpoint = endpoint
    
    @classmethod
    async def bind(cls, addr_or_path: str) -> 'RepSocket':
        endpoint = _to_ipc(addr_or_path)
        _ensure_parent(endpoint)
        s = _CTX.socket(zmq.REP)
        s.setsockopt(zmq.LINGER, 0)
        s.bind(endpoint)
        log.info('REP bound: %s', endpoint)
        return cls(s, endpoint)
    
    async def recv(self, *, timeout: Optional[float] = None) -> Dict[str, Any]:
        if timeout:
            buf = await asyncio.wait_for(self._sock.recv(), timeout=timeout)
        else:
            buf = await self._sock.recv()
        return _unpack(buf)
    
    async def send(self, payload: Dict[str, Any], *, timeout: Optional[float] = None) -> None:
        if timeout:
            await asyncio.wait_for(self._sock.send(_pack(payload)), timeout=timeout)
        else:
            await self._sock.send(_pack(payload))
    
    async def close(self) -> None:
        try:
            self._sock.close(0)
        except:
            pass

async def shutdown_sockets(*sockets: Any) -> None:
    for s in sockets:
        try:
            await s.close()
        except:
            pass