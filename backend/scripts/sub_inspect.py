import asyncio
from backend.core.zmq_bus import SubSocket
from backend.core.config import get_config

CFG = get_config()

async def run():
    sub = await SubSocket.connect(CFG.md_pub_ipc, topics=['prices.'])
    n = 0
    async for msg in sub:
        payload = msg['payload']
        print(f"[{msg['type']}] ts={msg['ts']} sec={payload['security_id']} mid={payload['mid']}")
        n += 1
        if n > 10:
            break
    await sub.close()
    
if __name__ == '__main__':
    asyncio.run(run())