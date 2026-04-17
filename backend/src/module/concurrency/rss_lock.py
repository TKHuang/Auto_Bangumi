"""Per-RSS asyncio lock registry with skip-if-held semantics (spec §9.1).

RSS refresh (cron) and manual refresh API share this registry. If a refresh
is already running for an rss_id, new attempts return None instead of
queueing — the caller logs and skips.
"""
from __future__ import annotations

import asyncio
from typing import Optional


class RssLockRegistry:
    def __init__(self) -> None:
        self._locks: dict[int, asyncio.Lock] = {}
        self._registry_mutex = asyncio.Lock()

    async def try_acquire(self, rss_id: int) -> Optional[asyncio.Lock]:
        """Return the acquired lock on success, or None if already held.

        Caller is responsible for calling `.release()` exactly once.
        """
        async with self._registry_mutex:
            lock = self._locks.setdefault(rss_id, asyncio.Lock())
            if lock.locked():
                return None
            await lock.acquire()
            return lock
