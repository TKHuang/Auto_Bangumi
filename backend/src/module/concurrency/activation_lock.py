"""Process-wide bangumi activation locks."""

from __future__ import annotations

import asyncio
from typing import Optional

_activation_locks: dict[int, asyncio.Lock] = {}


async def try_acquire_bangumi_activation_lock(
    bangumi_id: int,
) -> Optional[asyncio.Lock]:
    """Acquire a per-bangumi activation lock or return None if it is held.

    Pending-review activation performs external downloader I/O after updating
    DB state. A duplicated request can otherwise submit the same selected
    torrents twice before either request marks them downloaded.
    """
    lock = _activation_locks.get(bangumi_id)
    if lock is None:
        lock = asyncio.Lock()
        _activation_locks[bangumi_id] = lock

    if lock.locked():
        return None

    await lock.acquire()
    return lock
