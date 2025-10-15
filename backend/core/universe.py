from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
import json
import numpy as np
from typing import List, Dict, Optional
from backend.core.schemas import Exchange, Security, GBMParams, CorrelationMatrix

DATA_PATH = Path(__file__).resolve().parents[1] / 'data' / 'universe.json'


@dataclass
class Universe:
    securities: List[Security]
    exchanges: Dict[str, Exchange]
    correlation: Optional[CorrelationMatrix] = None


def _nearest_positive_definite(A: np.ndarray, epsilon: float = 1e-8) -> np.ndarray:
    """Return the nearest positive-definite matrix to A."""
    B = (A + A.T) / 2
    _, s, V = np.linalg.svd(B)
    H = np.dot(V.T, np.dot(np.diag(s), V))
    A2 = (B + H) / 2
    A3 = (A2 + A2.T) / 2
    # Ensure positive definiteness by shifting eigenvalues if needed
    eigvals, _ = np.linalg.eigh(A3)
    min_eig = np.min(eigvals)
    if min_eig < epsilon:
        A3 += np.eye(A.shape[0]) * (-min_eig + epsilon)
    return A3


def _generate_correlation_matrix(securities: List[Security]) -> CorrelationMatrix:
    stocks = [s for s in securities if s.type == "Equity"]
    ids = [s.id for s in stocks]
    n = len(stocks)
    matrix = np.eye(n)

    for i in range(n):
        for j in range(i + 1, n):
            si, sj = stocks[i], stocks[j]
            if si.region == sj.region and si.sector == sj.sector:
                rho = 0.8
            elif si.region == sj.region:
                rho = 0.6
            elif si.sector == sj.sector:
                rho = 0.4
            else:
                rho = 0.2
            # small random noise to avoid singularities
            rho += np.random.normal(0, 0.02)
            rho = np.clip(rho, 0.05, 0.95)
            matrix[i, j] = matrix[j, i] = rho

    # ✅ ensure symmetric positive definiteness
    matrix = _nearest_positive_definite(matrix)

    corr_dict = {ids[i]: {ids[j]: float(matrix[i, j]) for j in range(n)} for i in range(n)}
    return CorrelationMatrix(matrix=corr_dict)


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
    uni = Universe(securities=securities, exchanges=exchanges)
    uni.correlation = _generate_correlation_matrix(uni.securities)
    return uni


def _load_from_json(path: Path) -> Universe:
    data = json.loads(path.read_text())
    exchanges = {e['id']: Exchange(**e) for e in data['exchanges']}
    securities = [Security(**s) for s in data['securities']]
    correlation = None
    if 'correlation' in data:
        correlation = CorrelationMatrix(**data['correlation'])
    return Universe(securities=securities, exchanges=exchanges, correlation=correlation)


def _save_to_json(path: Path, uni: Universe) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        'exchanges': [e.model_dump() for e in uni.exchanges.values()],
        'securities': [s.model_dump() for s in uni.securities],
    }
    if uni.correlation is not None:
        payload['correlation'] = uni.correlation.model_dump()
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
