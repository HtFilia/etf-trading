import asyncio
from backend.core.zmq_bus import SubSocket
from backend.core.config import get_config
from backend.core.logging import get_logger, init_logging

CFG = get_config()
init_logging(__name__)
log = get_logger(__name__)


async def run():
    sub = await SubSocket.connect(CFG.md_ipc, topics=['prices.'])
    n = 0
    async for msg in sub:
        log.info(msg)
        n += 1
        if n > 10:
            break
    await sub.close()


if __name__ == '__main__':
    asyncio.run(run())
