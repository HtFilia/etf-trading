from __future__ import annotations
from datetime import datetime, timezone, time
from zoneinfo import ZoneInfo
from typing import Dict, List, Optional
from backend.core.schemas import Exchange
from backend.core.config import get_config

CFG = get_config()


def _parse_hhmm(hhmm: str) -> time:
    hh, mm = hhmm.split(':')
    return time(int(hh), int(mm))


def is_open(exchange: Exchange, dt: Optional[datetime] = None) -> bool:
    if CFG.dev_mode:
        return True
    if dt is None:
        dt = datetime.now(timezone.utc)
    dt_local = dt.astimezone(ZoneInfo(exchange.timezone))
    if dt_local.weekday() not in exchange.trading_days:
        return False
    t_open = _parse_hhmm(exchange.open_time)
    t_close = _parse_hhmm(exchange.close_time)
    return t_open <= dt_local.time() <= t_close


def to_exchange_map(exhcanges: List[Exchange]) -> Dict[str, Exchange]:
    return {ex.id: ex for ex in exhcanges}
