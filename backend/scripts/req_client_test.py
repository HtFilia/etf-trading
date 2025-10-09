import asyncio
from backend.core.zmq_bus import ReqSocket
from backend.core.config import get_config
from backend.core.logging import get_logger, init_logging

CFG = get_config()
init_logging(__name__)
log = get_logger(__name__)

async def main():
    req = await ReqSocket.connect(CFG.pcf_reqrep_ipc)
    resp = await req.send_and_recv({'hello': 'world'})
    log.info('client got %s', resp)

if __name__ == '__main__':
    asyncio.run(main())