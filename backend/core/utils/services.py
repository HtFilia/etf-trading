from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Iterable, Optional
from backend.core.utils.signals import install_sig_handlers, graceful_shutdown
from backend.core.logging import init_logging, get_logger

AsyncFn = Callable[[], Awaitable[None]]
AsyncInitFn = Callable[[], Awaitable[None]]


async def run_service(
    *,
    name: str,
    main: AsyncFn,
    init: Optional[AsyncInitFn] = None,
    background: Optional[Iterable[AsyncFn]] = None,
    on_shutdown: Optional[Iterable[AsyncFn]] = None,
) -> None:
    init_logging(name)
    logger = get_logger(name)

    stop = asyncio.Event()
    install_sig_handlers(stop)

    if init:
        logger.info('Initializing %s ...', name)
        await init()
        logger.info('Initialization complete')

    tasks = []
    tasks.append(asyncio.create_task(main(), name=f'{name}:main'))
    if background:
        for fn in background:
            tasks.append(asyncio.create_task(fn(), name=f'{name}:bg'))

    logger.info('%s started (%d task(s))', name, len(tasks))

    try:
        async with graceful_shutdown(*tasks):
            await stop.wait()
    except KeyboardInterrupt:
        pass
    finally:
        logger.info('Shutting down %s ...', name)
        if on_shutdown:
            for hook in on_shutdown:
                try:
                    await hook()
                except Exception as e:
                    logger.exception('Shutdown hook failed: %s', e)
        logger.info('%s stopped', name)
