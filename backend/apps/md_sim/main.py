import asyncio, time
import random
from backend.core.zmq_bus import PubSocket
from backend.core.universe import load_universe
from backend.core.timecal import is_open
from backend.core.schemas import Security, PriceTick


PUB_ADDR = 'ipc:///tmp/etf-trading/md_pub.sock'

def _simulate_tick(sec: Security) -> PriceTick:
    mid = 100.0 + random.uniform(-10, 10)
    spread = random.uniform(0, 3)
    return PriceTick(
        security_id=sec.id,
        bid=round(mid-spread, 4),
        ask=round(mid+spread, 4),
        mid=round(mid, 4),
        last=round(mid, 4),
        source='sim',
    )

async def run():
    pub = await PubSocket.bind(PUB_ADDR)
    universe = load_universe()
    while True:
        now = time.time()
        for sec in universe.securities:
            exchange = universe.exchanges[sec.exchange_id]
            if is_open(exchange, now):
                tick = _simulate_tick(sec)
                await pub.send('prices.tick', tick, version=1)
        await asyncio.sleep(1.0)

if __name__ == '__main__':
    asyncio.run(run())