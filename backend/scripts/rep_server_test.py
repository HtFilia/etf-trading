import asyncio
from backend.core.zmq_bus import RepSocket
from backend.core.config import get_config
from backend.core.logging import get_logger, init_logging

CFG = get_config()
init_logging(__name__)
log = get_logger(__name__)


async def main():
    rep = await RepSocket.bind(CFG.pcf_reqrep_ipc)
    log.info('REP listening %s', CFG.pcf_reqrep_ipc)
    while True:
        req = await rep.recv()
        log.info('server got: %s', req)
        await rep.send({'ok': True, 'echo': req})


if __name__ == '__main__':
    asyncio.run(main())
