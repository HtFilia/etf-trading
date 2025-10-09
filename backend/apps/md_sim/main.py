import asyncio
import os
from datetime import datetime, timezone
import random
from backend.core.zmq_bus import PubSocket, shutdown_sockets
from backend.core.universe import load_universe
from backend.core.timecal import is_open
from backend.core.schemas import Security, PriceTick
from backend.core.utils.signals import install_sig_handlers, graceful_shutdown

PUB_ADDR = 'ipc:///tmp/etf-trading/md_pub.sock'
TICK_INTERVAL = float(os.environ.get('TICK_INTERVAL_MS', '1000.0')) / 1000

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

async def publish_ticks(pub: PubSocket):
    universe = load_universe()
    while True:
        now = datetime.now(timezone.utc)
        for sec in universe.securities:
            exchange = universe.exchanges[sec.exchange_id]
            if is_open(exchange, now):
                tick = _simulate_tick(sec)
                await pub.send('prices.tick', tick, version=1)
        await asyncio.sleep(TICK_INTERVAL)          

async def run():
    stop = asyncio.Event()
    install_sig_handlers(stop)
    
    pub = await PubSocket.bind(PUB_ADDR)
    producer = asyncio.create_task(publish_ticks(pub))
    
    async with graceful_shutdown(producer):
        await stop.wait()
    
    await shutdown_sockets(pub)
    
if __name__ == '__main__':
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass