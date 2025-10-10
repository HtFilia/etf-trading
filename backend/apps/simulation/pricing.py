from __future__ import annotations
import asyncio
from typing import Optional, Dict, Any
from backend.core.config import get_config
from backend.core.zmq_bus import SubSocket, PubSocket, ReqSocket, shutdown_sockets
from backend.core.utils.services import run_service
from backend.core.logging import get_logger

CFG = get_config()
log = get_logger(__name__)

_sub: Optional[SubSocket] = None
_pub: Optional[PubSocket] = None
_pcf: Optional[ReqSocket] = None

_state: Dict[str, Any] = {
    'ticks': {},  # security_id -> last price tick
    'fx_spot': {},  # pair -> spot
    'fx_fwd': {},  # pair -> points curve
}


async def init() -> None:
    global _sub, _pub, _pcf
    _sub = await SubSocket.connect(CFG.md_pub_ipc, topics=['prices.', 'fx.'])
    _pub = await PubSocket.bind(CFG.pricing_pub_ipc)
    _pcf = await ReqSocket.connect(CFG.pcf_reqrep_ipc)
    log.info(
        'pricing connected',
        extra={'md_sub': CFG.md_pub_ipc, 'pricing_pub': CFG.pricing_pub_ipc, 'pcf_reqrep': CFG.pcf_reqrep_ipc},
    )


async def consume_bus() -> None:
    assert _sub is not None
    async for msg in _sub:
        t = msg['type']
        p = msg['payload']
        if t == 'prices.tick':
            _state['ticks'][p['security_id']] = p
        elif t == 'fx.spot':
            _state['fx_spot'][p['pair']] = p['spot']
        elif t == 'fx.forwards':
            _state['fx_fwd'][p['pair']] = p['points']


async def publish_inav() -> None:
    assert _pub is not None
    sc_id = 'SC_SIM'
    inav = 100.0
    low, high = 99.9, 100.1
    while True:
        await _pub.send('inav.tick', {'share_class_id': sc_id, 'inav': inav, 'band_low': low, 'band_high': high})
        await asyncio.sleep(CFG.tick_interval)


async def shutdown() -> None:
    await shutdown_sockets(_sub, _pub, _pcf)
    log.info('pricing shutdown complete')


async def run():
    await run_service(
        name='pricing',
        init=init,
        main=publish_inav,
        background=[consume_bus],
        on_shutdown=[shutdown],
    )


if __name__ == '__main__':
    asyncio.run(run())
