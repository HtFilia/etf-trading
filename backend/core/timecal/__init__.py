from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo
from typing import Dict, List
from backend.core.schemas import Exchange

def _parse_hhmm(hhmm: str) -> time:
    hh, mm = hhmm.split(':')
    return time(int(hh), int(mm))

def is_open(exchange: Exchange, epoch_seconds: float) -> bool:
    dt_utc = datetime.utcfromtimestamp(epoch_seconds).replace(tzinfo=ZoneInfo('UTC'))
    dt_local = dt_utc.astimezone(ZoneInfo(exchange.timezone))
    if dt_local.weekday() not in exchange.trading_days:
        return False
    t_open = _parse_hhmm(exchange.open_time)
    t_close = _parse_hhmm(exchange.close_time)
    return (dt_local.time() >= t_open) and (dt_local.time() <= t_close)

def to_exchange_map(exhcanges: List[Exchange]) -> Dict[str, Exchange]:
    return {ex.id: ex for ex in exhcanges}