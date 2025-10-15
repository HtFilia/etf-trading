# backend/core/serialization.py
from __future__ import annotations

import json
from dataclasses import is_dataclass, asdict
from typing import Any, Dict

try:
    import msgpack
except ImportError:
    msgpack = None

try:
    import numpy as np
except ImportError:
    np = None


def to_plain(obj: Any) -> Any:
    """Convert arbitrary Python / dataclass / numpy / pydantic structures to plain Python."""
    try:
        from pydantic import BaseModel
        if isinstance(obj, BaseModel):
            return obj.model_dump()
    except ImportError:
        pass

    if is_dataclass(obj):
        return {k: to_plain(v) for k, v in asdict(obj).items()}

    if np is not None:
        if isinstance(obj, np.generic):
            return obj.item()
        if isinstance(obj, np.ndarray):
            return obj.tolist()

    if isinstance(obj, dict):
        return {k: to_plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_plain(v) for v in obj]
    return obj


def pack(obj: Dict[str, Any]) -> bytes:
    """Serialize dict-like object into bytes (msgpack preferred, JSON fallback)."""
    obj = to_plain(obj)
    if msgpack:
        return msgpack.packb(obj, default=to_plain, use_bin_type=True, strict_map_key=False)
    return json.dumps(obj, separators=(",", ":")).encode("utf-8")


def unpack(buf: bytes) -> Dict[str, Any]:
    """Deserialize bytes into a Python dict."""
    if msgpack:
        return msgpack.unpackb(buf, raw=False)
    return json.loads(buf.decode("utf-8"))
