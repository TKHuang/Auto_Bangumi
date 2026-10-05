"""Process-wide rename lock shared by scheduler jobs and manual APIs."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Optional

_rename_lock = asyncio.Lock()


async def try_acquire_rename_lock() -> Optional[asyncio.Lock]:
    """Acquire the shared rename lock or return None if it is already held.

    Single-process asyncio is cooperative: there is no yield point between the
    synchronous ``locked()`` check and the ``acquire()`` call below
    (``asyncio.Lock.acquire()`` returns immediately when uncontested), so two
    coroutines cannot both pass the check and then both end up blocking. This
    pattern would NOT be safe under multi-threaded execution, but FastAPI +
    a single uvicorn worker keeps everything on one event loop.

    For multi-worker deployments the lock would need to migrate to a file-
    or DB-based lock; left as future work.
    """
    if _rename_lock.locked():
        return None
    await _rename_lock.acquire()
    return _rename_lock


@asynccontextmanager
async def rename_lock_guard() -> AsyncIterator[Optional[asyncio.Lock]]:
    """Hold the shared rename lock for the ``async with`` block.

    Yields ``None`` when another rename holds the lock; the caller then
    returns its own busy response. The lock is released on any exit.
    """
    lock = await try_acquire_rename_lock()
    try:
        yield lock
    finally:
        if lock is not None:
            lock.release()
