# backend/core/zmq_bus.py
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Iterable, Optional

import zmq
import zmq.asyncio

from backend.core.config import get_config
from backend.core.serialization import pack, unpack, to_plain

log = logging.getLogger(__name__)

_CTX = zmq.asyncio.Context.instance()
CFG = get_config()

# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _utc_now() -> datetime:
    """Return current UTC time with timezone."""
    return datetime.now(timezone.utc)


def _now_ms() -> int:
    """Return current UTC time in milliseconds since epoch."""
    return int(_utc_now().timestamp() * 1000)


def _envelope(topic: str, payload: Dict[str, Any], version: int = 1) -> Dict[str, Any]:
    """Create a standardized message envelope with UTC timestamp and UUID."""
    return {
        "id": str(uuid.uuid4()),
        "type": topic,
        "ts": _now_ms(),
        "datetime": _utc_now().isoformat(),
        "v": version,
        "payload": payload,
    }


def _resolve_ipc(addr_or_path: str) -> str:
    """
    Resolve a socket path to a full IPC endpoint.
    - If it starts with ipc:// or tcp:// → use as-is.
    - If it’s an absolute file path → prefix with ipc://
    - Otherwise → relative to CFG.zmq_dir
    """
    if addr_or_path.startswith(("ipc://", "tcp://")):
        return addr_or_path
    if addr_or_path.startswith("/"):
        return f"ipc://{addr_or_path}"
    return f"ipc://{Path(CFG.zmq_dir) / addr_or_path}"


def _ensure_parent(endpoint_ipc: str) -> Optional[Path]:
    """Ensure the IPC file’s directory exists and remove stale socket file."""
    if not endpoint_ipc.startswith("ipc://"):
        return None
    fs_path = Path(endpoint_ipc.replace("ipc://", ""))
    fs_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if fs_path.exists():
            fs_path.unlink()
    except Exception as e:
        log.warning("Could not unlink stale IPC path %s: %s", fs_path, e)
    return fs_path


def shutdown_zmq_context() -> None:
    """Gracefully terminate the global ZMQ context."""
    global _CTX
    try:
        _CTX.term()
        log.info("ZMQ context terminated.")
    except Exception as e:
        log.warning("Error terminating ZMQ context: %s", e)


# ---------------------------------------------------------------------------
# PUB / SUB sockets
# ---------------------------------------------------------------------------

class PubSocket:
    def __init__(self, sock: zmq.asyncio.Socket, endpoint: str):
        self._sock = sock
        self.endpoint = endpoint

    @classmethod
    async def bind(cls, addr_or_path: str) -> "PubSocket":
        """
        Bind a PUB socket to the given address.
        Accepts:
          - ipc:///tmp/...  (already fully resolved)
          - /tmp/...        (absolute file path)
          - md.sock         (relative, resolved via CFG.zmq_dir)
        """
        endpoint = _resolve_ipc(addr_or_path)
        _ensure_parent(endpoint)

        s = _CTX.socket(zmq.PUB)
        s.setsockopt(zmq.LINGER, 0)
        s.bind(endpoint)
        log.info("PUB bound: %s", endpoint)
        return cls(s, endpoint)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    async def send(self, topic: str, payload: Dict[str, Any], version: int = 1) -> None:
        env = _envelope(topic=topic, payload=to_plain(payload), version=version)
        try:
            await self._sock.send_multipart([topic.encode("utf-8"), pack(env)])
        except zmq.ZMQError as e:
            log.warning("ZMQ PUB send failed on %s: %s", self.endpoint, e)

    async def close(self) -> None:
        try:
            self._sock.close(0)
        except Exception as e:
            log.debug("Error closing PUB socket: %s", e)


class SubSocket(AsyncIterator[Dict[str, Any]]):
    def __init__(self, sock: zmq.asyncio.Socket, endpoint: str, topics: list[str]):
        self._sock = sock
        self.endpoint = endpoint
        self._topics = topics or [""]

    @classmethod
    async def connect(cls, addr_or_path: str, topics: Optional[Iterable[str]] = None) -> "SubSocket":
        endpoint = _resolve_ipc(addr_or_path)

        s = _CTX.socket(zmq.SUB)
        s.setsockopt(zmq.LINGER, 0)
        s.connect(endpoint)

        tlist = list(topics) if topics else [""]
        for t in tlist:
            s.setsockopt_string(zmq.SUBSCRIBE, t)

        log.info("SUB connected: %s (topics=%s)", endpoint, tlist)
        return cls(s, endpoint, tlist)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    def __aiter__(self):
        return self

    async def __anext__(self) -> Dict[str, Any]:
        try:
            topic_b, payload_b = await self._sock.recv_multipart()
            topic = topic_b.decode("utf-8", errors="ignore")
            env = unpack(payload_b)
            env.setdefault("type", topic)
            return env
        except (asyncio.CancelledError, zmq.error.ContextTerminated):
            raise StopAsyncIteration
        except zmq.ZMQError as e:
            log.warning("ZMQ SUB recv failed: %s", e)
            raise StopAsyncIteration

    async def close(self) -> None:
        try:
            self._sock.close(0)
        except Exception as e:
            log.debug("Error closing SUB socket: %s", e)


# ---------------------------------------------------------------------------
# REQ / REP sockets
# ---------------------------------------------------------------------------

class ReqSocket:
    def __init__(self, sock: zmq.asyncio.Socket, endpoint: str):
        self._sock = sock
        self.endpoint = endpoint
        self._lock = asyncio.Lock()

    @classmethod
    async def connect(cls, addr_or_path: str) -> "ReqSocket":
        endpoint = _resolve_ipc(addr_or_path)
        s = _CTX.socket(zmq.REQ)
        s.setsockopt(zmq.LINGER, 0)
        s.connect(endpoint)
        log.info("REQ connected: %s", endpoint)
        return cls(s, endpoint)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    async def send_and_recv(self, payload: Dict[str, Any], *, timeout: Optional[float] = None) -> Dict[str, Any]:
        async with self._lock:
            try:
                await self._sock.send(pack(payload))
                if timeout:
                    buf = await asyncio.wait_for(self._sock.recv(), timeout=timeout)
                else:
                    buf = await self._sock.recv()
                return unpack(buf)
            except (zmq.ZMQError, asyncio.TimeoutError) as e:
                log.warning("REQ send/recv error on %s: %s", self.endpoint, e)
                return {"error": str(e)}

    async def close(self) -> None:
        try:
            self._sock.close(0)
        except Exception as e:
            log.debug("Error closing REQ socket: %s", e)


class RepSocket:
    def __init__(self, sock: zmq.asyncio.Socket, endpoint: str):
        self._sock = sock
        self.endpoint = endpoint

    @classmethod
    async def bind(cls, addr_or_path: str) -> "RepSocket":
        endpoint = _resolve_ipc(addr_or_path)
        _ensure_parent(endpoint)

        s = _CTX.socket(zmq.REP)
        s.setsockopt(zmq.LINGER, 0)
        s.bind(endpoint)
        log.info("REP bound: %s", endpoint)
        return cls(s, endpoint)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    async def recv(self, *, timeout: Optional[float] = None) -> Dict[str, Any]:
        try:
            if timeout:
                buf = await asyncio.wait_for(self._sock.recv(), timeout=timeout)
            else:
                buf = await self._sock.recv()
            return unpack(buf)
        except (zmq.ZMQError, asyncio.TimeoutError) as e:
            log.warning("REP recv error on %s: %s", self.endpoint, e)
            return {"error": str(e)}

    async def send(self, payload: Dict[str, Any], *, timeout: Optional[float] = None) -> None:
        try:
            if timeout:
                await asyncio.wait_for(self._sock.send(pack(payload)), timeout=timeout)
            else:
                await self._sock.send(pack(payload))
        except (zmq.ZMQError, asyncio.TimeoutError) as e:
            log.warning("REP send error on %s: %s", self.endpoint, e)

    async def close(self) -> None:
        try:
            self._sock.close(0)
        except Exception as e:
            log.debug("Error closing REP socket: %s", e)


# ---------------------------------------------------------------------------
# Shutdown utility
# ---------------------------------------------------------------------------

async def shutdown_sockets(*sockets: Any) -> None:
    """Close all provided sockets and terminate context."""
    for s in sockets:
        try:
            await s.close()
        except Exception as e:
            log.debug("Error closing socket: %s", e)
    shutdown_zmq_context()
