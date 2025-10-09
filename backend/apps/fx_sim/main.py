from __future__ import annotations
import asyncio, math, random
from datetime import datetime, timezone
from typing import Optional, Dict
from backend.core.config import get_config
from backend.core.logging import get_logger
from backend.core.zmq_bus import PubSocket, shutdown_sockets
from backend.core.utils.services import run_service

CFG = get_config()
log = get_logger(__name__)

_pub: Optional[PubSocket] = None
PAIRS = ['EURUSD', 'USDJPY', 'EURGBP']

async def init() -> None:
    global _pub
    _pub = await PubSocket.bind(CFG.md_pub_ipc)
    log.info('fx_sim publishing on md_pub', extra={'endpoint': CFG.md_pub_ipc})

def _step_spot(prev: float) -> float:
    return round(prev * math.exp(random.gauss(0, 0.0005)), 6)

def _forwards_from_spot(spot: float) -> Dict[str, float]:
    return {
        'ON': round(spot * 0.0001, 6),
        '1W': round(spot * 0.0006, 6),
        '1M': round(spot * 0.0025, 6),
        '3M': round(spot * 0.0070, 6),
    }

async def publisher() -> None:
    assert _pub is not None
    spots = {'EURUSD': 1.08, 'USDJPY': 150.0, 'EURGBP': 0.86}
    while True:
        now = datetime.now(timezone.utc).isoformat()
        for pair in PAIRS:
            spots[pair] = _step_spot(spots[pair])
            await _pub.send('fx.spot', {'pair': pair, 'ts': now, 'spot': spots[pair]}, version=1)
            await _pub.send('fx.forwards', {'pair': pair, 'ts': now, 'points': _forwards_from_spot(spots[pair])}, version=1)
        await asyncio.sleep(CFG.tick_interval)

async def shutdown() -> None:
    await shutdown_sockets(_pub)
    log.info('fx_sim shutdown complete')

async def run():
    await run_service(
        name='fx_sim',
        init=init,
        main=publisher,
        on_shutdown=[shutdown],
    )

if __name__ == '__main__':
    asyncio.run(run())