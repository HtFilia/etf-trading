from __future__ import annotations
import asyncio
import random
import math
import numpy as np
from datetime import datetime, timezone
from typing import Optional, Dict, Tuple, List, AsyncGenerator

from backend.core.config import get_config
from backend.core.zmq_bus import PubSocket, shutdown_sockets
from backend.core.universe import load_universe, Universe
from backend.core.timecal import is_open
from backend.core.schemas import Security, PriceTick
from backend.core.utils.services import run_service
from backend.core.logging import get_logger

CFG = get_config()
log = get_logger(__name__)

# --- Global state ---
_pub: Optional[PubSocket] = None
_universe: Optional[Universe] = None
_equities: List[Security] = []
_etfs: List[Security] = []
_exchanges: Dict[str, str] = {}

_gbm_state: Dict[str, float] = {}
_gbm_params: Dict[str, Tuple[float, float]] = {}

_corr_L: Optional[np.ndarray] = None
_corr_ids: Optional[List[str]] = None


# ================================================================
#   Initialization helpers
# ================================================================

def _init_gbm_state(universe: Universe) -> None:
    """Initialize GBM states (μ, σ, S₀) for all securities."""
    for sec in universe.securities:
        mu = sec.gbm_params.mu if sec.gbm_params else random.uniform(0.05, 0.15)
        sigma = sec.gbm_params.sigma if sec.gbm_params else random.uniform(0.15, 0.35)
        S0 = sec.gbm_params.s0 if sec.gbm_params else 100.0 + random.uniform(-5, 5)
        _gbm_state[sec.id] = S0
        _gbm_params[sec.id] = (mu, sigma)


def _init_correlation(universe: Universe) -> None:
    """Precompute Cholesky decomposition for correlated equities."""
    global _corr_L, _corr_ids
    if universe.correlation is None:
        _corr_L, _corr_ids = None, None
        return

    equities = [s for s in universe.securities if s.type == "Equity"]
    _corr_ids = [s.id for s in equities]
    mat = np.array([[universe.correlation.matrix[i][j] for j in _corr_ids] for i in _corr_ids])
    _corr_L = np.linalg.cholesky(mat)


# ================================================================
#   GBM evolution step
# ================================================================

def _gbm_step(S: np.ndarray, mu: np.ndarray, sigma: np.ndarray, Z: np.ndarray, dt_years: float) -> np.ndarray:
    """Vectorized GBM step."""
    return S * np.exp((mu - 0.5 * sigma**2) * dt_years + sigma * math.sqrt(dt_years) * Z)


# ================================================================
#   Tick generator
# ================================================================

async def generate_ticks(dt: float) -> AsyncGenerator[PriceTick, None]:
    """Unified generator for equities (correlated) and ETFs (independent)."""
    global _universe, _corr_L, _corr_ids, _gbm_state, _gbm_params

    now = datetime.now(timezone.utc)
    dt_years = dt / (252 * 6.5 * 3600)

    # --- Equities ---
    open_equities = [s for s in _equities if is_open(_exchanges[s.exchange_id], now)]
    if open_equities:
        mus = np.array([_gbm_params[s.id][0] for s in open_equities])
        sigmas = np.array([_gbm_params[s.id][1] for s in open_equities])
        S = np.array([_gbm_state[s.id] for s in open_equities])

        if _corr_L is not None:
            # Correlated normal shocks
            Z_uncorr = np.random.normal(size=len(_corr_ids))
            Z_all = _corr_L @ Z_uncorr
            idx_map = {sid: i for i, sid in enumerate(_corr_ids)}
            Z = np.array([Z_all[idx_map[s.id]] for s in open_equities])
        else:
            Z = np.random.normal(size=len(open_equities))

        S_next = _gbm_step(S, mus, sigmas, Z, dt_years)
        for i, sec in enumerate(open_equities):
            _gbm_state[sec.id] = S_next[i]
            spread = random.uniform(0.01, 0.05) * S_next[i]
            yield PriceTick(
                security_id=sec.id,
                bid=round(S_next[i] - spread / 2, 4),
                ask=round(S_next[i] + spread / 2, 4),
                mid=round(S_next[i], 4),
                last=round(S_next[i], 4),
                source="sim",
            )

    # --- ETFs ---
    open_etfs = [s for s in _etfs if is_open(_exchanges[s.exchange_id], now)]
    if open_etfs:
        for sec in open_etfs:
            mu, sigma = _gbm_params[sec.id]
            S = _gbm_state[sec.id]
            Z = np.random.normal()
            S_next = _gbm_step(np.array([S]), np.array([mu]), np.array([sigma]), np.array([Z]), dt_years)[0]
            _gbm_state[sec.id] = S_next
            spread = random.uniform(0.01, 0.05) * S_next
            yield PriceTick(
                security_id=sec.id,
                bid=round(S_next - spread / 2, 4),
                ask=round(S_next + spread / 2, 4),
                mid=round(S_next, 4),
                last=round(S_next, 4),
                source="sim",
            )


# ================================================================
#   Service lifecycle
# ================================================================

async def init() -> None:
    global _pub, _universe, _equities, _etfs, _exchanges
    log.info("Initializing market data simulator...")

    _pub = await PubSocket.bind(CFG.md_ipc)
    log.info("md_sim bound", extra={"event": "bind", "endpoint": CFG.md_ipc})

    _universe = load_universe()
    _equities = [s for s in _universe.securities if s.type == "Equity"]
    _etfs = [s for s in _universe.securities if s.type == "ETF"]
    _exchanges = _universe.exchanges

    _init_gbm_state(_universe)
    _init_correlation(_universe)
    log.info("GBM and correlation structures initialized.")


async def producer() -> None:
    dt = CFG.tick_interval
    while True:
        async for tick in generate_ticks(dt):
            await _pub.send("prices.tick", tick, version=1)
        await asyncio.sleep(dt)


async def shutdown() -> None:
    await shutdown_sockets(_pub)
    log.info("md_sim shutdown complete")


async def run():
    await run_service(
        name="md_sim",
        init=init,
        main=producer,
        on_shutdown=[shutdown],
    )


if __name__ == "__main__":
    asyncio.run(run())
