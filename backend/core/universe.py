from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
import json
from typing import List, Dict

from backend.core.schemas import Exchange, Security, GBMParams

DATA_PATH = Path(__file__).resolve().parents[1] / 'data' / 'universe.json'


@dataclass
class Universe:
    securities: List[Security]
    exchanges: Dict[str, Exchange]


def _default_universe() -> Universe:
    """Generate a default synthetic universe with 10 equities and 2 ETFs, all on one exchange."""

    # --- 1️⃣ Single exchange definition ---
    exchange = Exchange(
        id="NYSE",
        name="New York Stock Exchange",
        timezone="America/New_York",
        open_time="09:30",
        close_time="16:00",
    )
    exchanges = {"NYSE": exchange}

    # --- 2️⃣ Controlled vocabularies ---
    sectors = [
        "Technology",
        "Financials",
        "Energy",
        "Healthcare",
        "Industrials",
        "Consumer Discretionary",
        "Materials",
        "Utilities",
    ]
    regions = ["US", "EU", "ASIA"]

    # --- 3️⃣ Random GBM hyperparameters ---
    def random_gbm_params(low_mu=0.05, high_mu=0.15, low_sigma=0.15, high_sigma=0.35) -> GBMParams:
        return GBMParams(
            mu=random.uniform(low_mu, high_mu),
            sigma=random.uniform(low_sigma, high_sigma),
            s0=random.uniform(80, 150),
            dt_mode="trading",
        )

    # --- 4️⃣ Generate 10 equities ---
    securities: List[Security] = []
    for i in range(10):
        sec = Security(
            id=f"EQ{i+1:02d}",
            ticker=f"EQ{i+1:02d}",
            name=f"Equity {i+1}",
            exchange_id="NYSE",
            currency="USD",
            type="Equity",
            sector=random.choice(sectors),
            region=random.choice(regions),
            gbm_params=random_gbm_params(),
        )
        securities.append(sec)

    # --- 5️⃣ Generate 2 ETFs (lower vol, lower drift) ---
    for i in range(2):
        sec = Security(
            id=f"ETF{i+1:02d}",
            ticker=f"ETF{i+1:02d}",
            name=f"ETF {i+1}",
            exchange_id="NYSE",
            currency="USD",
            type="ETF",
            sector="Financials",
            region="US",
            gbm_params=random_gbm_params(
                low_mu=0.03, high_mu=0.08, low_sigma=0.10, high_sigma=0.20
            ),
        )
        securities.append(sec)

    # --- 6️⃣ Build universe ---
    return Universe(securities=securities, exchanges=exchanges)


def _load_from_json(path: Path) -> Universe:
    data = json.loads(path.read_text())
    exchanges = {e['id']: Exchange(**e) for e in data['exchanges']}
    securities = [Security(**s) for s in data['securities']]
    return Universe(securities=securities, exchanges=exchanges)


def _save_to_json(path: Path, uni: Universe) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        'exchanges': [e.model_dump() for e in uni.exchanges.values()],
        'securities': [s.model_dump() for s in uni.securities],
    }
    path.write_text(json.dumps(payload, indent=2))


def load_universe() -> Universe:
    if DATA_PATH.exists():
        return _load_from_json(DATA_PATH)
    uni = _default_universe()
    try:
        _save_to_json(DATA_PATH, uni)
    except:
        pass
    return uni
