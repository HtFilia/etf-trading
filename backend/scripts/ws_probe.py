import asyncio
import json
import websockets
from backend.core.logging import get_logger

log = get_logger(__name__)


async def main():
    uri = 'ws://localhost:9080/stream'
    async with websockets.connect(uri, max_size=None) as ws:
        log.info('connected: %s', uri)
        for _ in range(10):
            msg = json.loads(await ws.recv())
            t = msg.get('type')
            p = msg.get('payload', {})
            if t == 'prices.tick':
                log.info('prices: %s = %f', p.get('security_id'), p.get('mid'))
            elif t == 'fx.spot':
                log.info('fx spot: %s = %f', p.get('pair'), p.get('spot'))
            elif t == 'inav.tick':
                log.info('inav: %s = %f', p.get('share_class_id'), p.get('inav'))
            else:
                log.info('other type: %s', t)
        log.info('done')


if __name__ == '__main__':
    asyncio.run(main())
