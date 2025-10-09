from __future__ import annotations
from typing import Optional, Dict, Any
import asyncio
from backend.core.config import get_config
from backend.core.logging import get_logger
from backend.core.zmq_bus import RepSocket, shutdown_sockets
from backend.core.utils.services import run_service

CFG = get_config()
log = get_logger(__name__)

_rep: Optional[RepSocket] = None
_state: Dict[str, Dict[str, Any]] = {
    'ETF_SP500': {
        'baskets': {
            'tracking': {'version': 1, 'lines': []},
            'holding': {'version': 1, 'lines': []},
            'creation': {'version': 1, 'lines': []},
            'redemption': {'version': 1, 'lines': []},
        },
        'costs': {
            'flat_create': 100.0,
            'flat_redeem': 100.0,
            'per_line_bps': 0.0,
            'per_venue_bps': {'XNAS': 0.2, 'XPAR': 0.3},
        },
        'stamp_duties': {
            'UK': {'buy': 50.0, 'sell': 0.0},
            'FR': {'buy': 40.0, 'sell': 0.0},
        },
    },
}

async def init() -> None:
    global _rep
    _rep = await RepSocket.bind(CFG.pcf_reqrep_ipc)
    log.info('pcf_sim bound', extra={'endpoint': CFG.pcf_reqrep_ipc})

async def server() -> None:
    assert _rep is not None
    while True:
        req = await _rep.recv()
        op = req.get('op')
        try:
            if op == 'list_etfs':
                await _rep.send({'ok': True, 'etfs': list(_state.keys())})
            elif op == 'get_pcf':
                etf_id = req['etf_id']
                await _rep.send({'ok': True, 'pcf': _state.get(etf_id)})
            elif op == 'set_costs':
                etf_id, costs = req['etf_id'], req['costs']
                _state.setdefault(etf_id, {}).setdefault('costs', {}).update(costs)
                await _rep.send({'ok': True})
            elif op == 'set_stamp_duties':
                etf_id, table = req['etf_id'], req['stamp_duties']
                _state.setdefault(etf_id, {}).setdefault('stamp_duties', {}).update(table)
                await _rep.send({'ok': True})
            elif op == 'set_baskets':
                etf_id, baskets = req['etf_id'], req['baskets']
                _state.setdefault(etf_id, {}).setdefault('baskets', {}).update(baskets)
                await _rep.send({'ok': True})
            else:
                await _rep.send({'ok': False, 'err': f'unknown_op:{op}'})
        except Exception as e:
            log.exception('pcf_sim error %s', e)
            await _rep.send({'ok': False, 'err': str(e)})

async def shutdown() -> None:
    await shutdown_sockets(_rep)
    log.info('pcf_sim shutdown complete')

async def run():
    await run_service(
        name='pcf_sim',
        init=init,
        main=server,
        on_shutdown=[shutdown],
    )

if __name__ == '__main__':
    asyncio.run(run())