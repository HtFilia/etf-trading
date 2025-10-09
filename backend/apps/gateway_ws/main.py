from __future__ import annotations
import asyncio
import uvicorn
from starlette.applications import Starlette
from starlette.websockets import WebSocket, WebSocketDisconnect
from backend.core.config import get_config
from backend.core.zmq_bus import SubSocket, ReqSocket
from backend.core.utils.services import run_service
from backend.core.logging import get_logger, integrate_uvicorn

CFG = get_config()
log = get_logger(__name__)
app = Starlette()

@app.websocket_route('/stream')
async def stream(ws: WebSocket):
    await ws.accept()
    subs = [
        await SubSocket.connect(CFG.md_pub_ipc, topics=['prices.', 'fx.']),
        await SubSocket.connect(CFG.pricing_pub_ipc, topics=['inav.']),
    ]
    calc = await ReqSocket.connect(CFG.calc_reqrep_ipc) if CFG.calc_reqrep_ipc else None
    log.info('WS client connected')
    
    async def forward(sub: SubSocket):
        try:
            async for msg in sub:
                await ws.send_json(msg)
        except (WebSocketDisconnect, RuntimeError):
            return
        
    async def rpc_loop():
        if not calc:
            try:
                while True:
                    await ws.receive_text()
            except WebSocketDisconnect:
                return
        else:
            try:
                while True:
                    req = await ws.receive_json()
                    if 'rpc' in req:
                        resp = await calc.send_and_recv(req)
                        try:
                            await ws.send_json({'rpc': req['rpc'], 'resp': resp})
                        except (WebSocketDisconnect, RuntimeError):
                            return
            except WebSocketDisconnect:
                return
    
    tasks = [asyncio.create_task(forward(s)) for s in subs]
    tasks.append(asyncio.create_task(rpc_loop()))
    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in pending:
            t.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
    finally:
        for s in subs:
            await s.close()
        if calc:
            await calc.close()
        try:
            await ws.close()
        except:
            pass
        log.info('WS client disconnected')

async def init():
    integrate_uvicorn(__name__)
    log.info('gateway initialized', extra={'event': 'init', 'ws_port': CFG.ws_port})

async def uvicorn_main():
    config = uvicorn.Config(
        app,
        host=CFG.ws_host,
        port=CFG.ws_port,
        log_level='info',
        lifespan='off',
    )
    server = uvicorn.Server(config)
    
    task = asyncio.create_task(server.serve(), name='gateway_ws:uvicorn')
    
    try:
        while not task.done():
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        server.should_exit = True
        try:
            await asyncio.wait_for(task, timeout=5.0)
        except asyncio.TimeoutError:
            pass
        return

async def run():
    await run_service(name='gateway_ws', init=init, main=uvicorn_main)

if __name__ == '__main__':
    asyncio.run(run())