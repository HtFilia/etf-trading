from __future__ import annotations

import asyncio
import signal
from contextlib import asynccontextmanager
from typing import Iterable, Optional

def install_sig_handlers(stop_event: asyncio.Event, signals: Optional[Iterable[int]] = None) -> None:
    loop = asyncio.get_running_loop()
    sigs = list(signals) if signals is not None else [signal.SIGINT, signal.SIGTERM]
    
    for sig in sigs:
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except (NotImplementedError, RuntimeError, AttributeError):
            pass

@asynccontextmanager
async def graceful_shutdown(*tasks: asyncio.Task):
    try:
        yield
    finally:
        for t in tasks:
            if not t.done():
                t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)