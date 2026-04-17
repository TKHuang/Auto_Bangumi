"""Async rate limiter with max-concurrent + min-interval gating (spec §9.2).

Used as an async context manager. Not thread-safe, but we run single-worker
uvicorn by design (spec §4).

Dynamic degradation (429/503 → halve concurrent, 10 successes → restore)
is layered on in Task 6 via record_result().
"""
from __future__ import annotations

import asyncio
import time


class RateLimiter:
    def __init__(self, max_concurrent: int, min_interval_ms: int):
        assert max_concurrent > 0
        assert min_interval_ms >= 0
        self._base_concurrent = max_concurrent
        self._sem = asyncio.Semaphore(max_concurrent)
        self._min_interval = min_interval_ms / 1000.0
        self._gate = asyncio.Lock()
        self._last_at: float = 0.0

    async def __aenter__(self) -> "RateLimiter":
        await self._sem.acquire()
        async with self._gate:
            now = time.monotonic()
            wait = self._last_at + self._min_interval - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_at = time.monotonic()
        return self

    async def __aexit__(self, *exc) -> None:
        self._sem.release()
