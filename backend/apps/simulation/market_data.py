from __future__ import annotations
import asyncio
from typing import Optional, Dict, Tuple
from datetime import datetime, timezone
import random
import math
import numpy as np
from backend.core.config import get_config
from backend.core.zmq_bus import PubSocket, shutdown_sockets
from backend.core.universe import load_universe
from backend.core.timecal import is_open
from backend.core.schemas import Security, PriceTick
from backend.core.utils.services import run_service
from backend.core.logging import get_logger

CFG = get_config()
log = get_logger(__name__)
_pub: Optional[PubSocket] = None

_gbm_state: Dict[str, float] = {} # security_id > last mid price
_gbm_params: Dict[str, Tuple[float, float]] = {} # security_id > (mu, sigma)

def _init_gbm_for_security(sec: Security) -> None:
    """Initialize GBM parameters and starting price for a given security."""
    # Randomize parameters a bit to differentiate stocks
    mu = random.uniform(0.05, 0.15)     # annualized drift ~ 5–15%
    sigma = random.uniform(0.15, 0.35)  # annualized volatility ~ 15–35%
    S0 = 100.0 + random.uniform(-5, 5)
    _gbm_state[sec.id] = S0
    _gbm_params[sec.id] = (mu, sigma)

async def init() -> None:
    global _pub
    _pub = await PubSocket.bind(CFG.md_pub_ipc)
    log.info('md_sim bound', extra={'event': 'bind', 'endpoint': CFG.md_pub_ipc})


def _simulate_tick(sec: Security, dt: float) -> PriceTick:
    """Simulate next price tick using Geometric Brownian Motion."""
    if sec.id not in _gbm_state:
        _init_gbm_for_security(sec)

    S = _gbm_state[sec.id]
    mu, sigma = _gbm_params[sec.id]

    # Convert dt to fraction of a year
    dt_years = dt / (252 * 6.5 * 3600)  # assume 252 trading days, 6.5h/day

    # Draw standard normal shock
    Z = np.random.normal()

    # GBM step
    S_next = S * math.exp((mu - 0.5 * sigma**2) * dt_years + sigma * math.sqrt(dt_years) * Z)

    # Store new price
    _gbm_state[sec.id] = S_next

    # Simulate a small random spread
    spread = random.uniform(0.01, 0.05) * S_next

    return PriceTick(
        security_id=sec.id,
        bid=round(S_next - spread / 2, 4),
        ask=round(S_next + spread / 2, 4),
        mid=round(S_next, 4),
        last=round(S_next, 4),
        source='sim',
    )


async def producer() -> None:
    assert _pub is not None
    universe = load_universe()
    dt = CFG.tick_interval
    while True:
        now = datetime.now(timezone.utc)
        for sec in universe.securities:
            exchange = universe.exchanges[sec.exchange_id]
            if is_open(exchange, now):
                tick = _simulate_tick(sec, dt)
                await _pub.send('prices.tick', tick, version=1)
        await asyncio.sleep(dt)


async def shutdown() -> None:
    await shutdown_sockets(_pub)
    log.info('md_sim shutdown complete')


async def run():
    await run_service(
        name='md_sim',
        init=init,
        main=producer,
        on_shutdown=[shutdown],
    )


if __name__ == '__main__':
    asyncio.run(run())
