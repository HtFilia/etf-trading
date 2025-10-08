import asyncio
from backend.core.zmq_bus import SubSocket

SUB_ADDR = 'ipc:///tmp/etf-trading/md_pub.sock'

async def run():
    sub = await SubSocket.connect(SUB_ADDR, topics=['prices.'])
    n = 0
    async for msg in sub:
        payload = msg['payload']
        print(f"[{msg['type']}] ts={msg['ts']} sec={payload['security_id']} mid={payload['mid']}")
        n += 1
        if n > 10:
            break

if __name__ == '__main__':
    asyncio.run(run())