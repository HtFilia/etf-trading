from __future__ import annotations
from typing import Optional, Literal, List, Dict
from pydantic import BaseModel, Field


class Exchange(BaseModel):
    id: str
    name: str
    timezone: str
    open_time: str
    close_time: str
    trading_days: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])


class GBMParams(BaseModel):
    mu: float = 0.10
    sigma: float = 0.20
    s0: float = 100.0
    dt_mode: Literal["trading", "calendar"] = "trading"


SectorLiteral = Literal[
    "Technology", "Financials", "Energy", "Utilities",
    "Healthcare", "Consumer Discretionary", "Consumer Staples",
    "Industrials", "Materials", "Telecommunications", "Real Estate"
]

RegionLiteral = Literal["US", "EU", "UK", "ASIA", "JAPAN", "EMEA", "LATAM"]
TypeLiteral = Literal["Equity", "ETF"]

class Security(BaseModel):
    id: str
    isin: Optional[str] = None
    ticker: str
    name: str
    exchange_id: str
    currency: str
    lot_size: int = 1
    type: TypeLiteral = "EQUITY"
    sector: Optional[SectorLiteral] = None
    region: Optional[RegionLiteral] = None
    gbm_params: Optional[GBMParams] = None


class PriceTick(BaseModel):
    security_id: str
    bid: float
    ask: float
    mid: float
    last: float
    source: str = "sim"


class BasketLine(BaseModel):
    security_id: str
    quantity: float
    currency: str


class Basket(BaseModel):
    version: int = 1
    divisor: float = 100.0
    composition: List[BasketLine] = Field(default_factory=list)


class ETFCosts(BaseModel):
    flat_create: float = 0.0
    flat_redeem: float = 0.0
    per_line_bps: float = 0.0
    per_venue_bps: Dict[str, float] = Field(default_factory=dict)

class ETFPCF(BaseModel):
    etf_id: str
    currency: str = "USD"
    baskets: Dict[str, Basket] = Field(default_factory=dict)
    costs: ETFCosts = Field(default_factory=ETFCosts)
    stamp_duties: Dict[str, Dict[str, float]] = Field(default_factory=dict)

class CorrelationMatrix(BaseModel):
    matrix: Dict[str, Dict[str, float]]
    method: Literal["sector_region", "custom"] = "sector_region"

