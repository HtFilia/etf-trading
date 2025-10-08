from __future__ import annotations
from typing import Optional, Literal
from pydantic import BaseModel, Field

class Exchange(BaseModel):
    id: str
    name: str
    timezone: str
    open_time: str
    close_time: str
    trading_days: set[int] = Field(default_factory=lambda: {0,1,2,3,4})

class Security(BaseModel):
    id: str
    isin: Optional[str] = None
    ticker: str
    name: str
    exchange_id: str
    currency: str
    lot_size: int = 1
    type: Literal['EQUITY', 'ETF'] = 'EQUITY'

class PriceTick(BaseModel):
    security_id: str
    bid: float
    ask: float
    mid: float
    last: float
    source: str = 'sim'