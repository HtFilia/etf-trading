from __future__ import annotations
import asyncio
from typing import Optional
from datetime import datetime, timezone
import random
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


async def init() -> None:
    global _pub
    _pub = await PubSocket.bind(CFG.md_pub_ipc)
    log.info('md_sim bound', extra={'event': 'bind', 'endpoint': CFG.md_pub_ipc})


def _simulate_tick(sec: Security) -> PriceTick:
    mid = 100.0 + random.uniform(-10, 10)
    spread = random.uniform(0, 3)
    return PriceTick(
        security_id=sec.id,
        bid=round(mid - spread, 4),
        ask=round(mid + spread, 4),
        mid=round(mid, 4),
        last=round(mid, 4),
        source='sim',
    )


async def producer() -> None:
    assert _pub is not None
    universe = load_universe()
    while True:
        now = datetime.now(timezone.utc)
        for sec in universe.securities:
            exchange = universe.exchanges[sec.exchange_id]
            if is_open(exchange, now):
                tick = _simulate_tick(sec)
                await _pub.send('prices.tick', tick, version=1)
        await asyncio.sleep(CFG.tick_interval)


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
