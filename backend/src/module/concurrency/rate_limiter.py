"""Async rate limiter with max-concurrent + min-interval gating +
dynamic degradation on 429/503 (spec §9.2, §9.3).

State machine:
  - Base state: max_concurrent = base_concurrent
  - 429/503 received: max_concurrent = max(1, max_concurrent // 2)
                      success_counter := 0
  - 10 consecutive 2xx while degraded: max_concurrent = base_concurrent

Used as an async context manager. Not thread-safe; single-worker assumption.
"""
from __future__ import annotations

import asyncio
import time

_SUCCESS_THRESHOLD = 10
_DEGRADE_STATUSES = (429, 503)


class RateLimiter:
    def __init__(self, max_concurrent: int, min_interval_ms: int):
        assert max_concurrent > 0
        assert min_interval_ms >= 0
        self._base_concurrent = max_concurrent
        self._current_concurrent = max_concurrent
        self._sem = asyncio.Semaphore(max_concurrent)
        self._min_interval = min_interval_ms / 1000.0
        self._gate = asyncio.Lock()
        self._last_at: float = 0.0
        self._success_counter = 0

    def current_concurrent(self) -> int:
        return self._current_concurrent

    def is_degraded(self) -> bool:
        return self._current_concurrent < self._base_concurrent

    def record_result(self, status: int) -> None:
        """Update state based on HTTP response status.

        Call this after every request (including the 200 path). 429/503 halve
        concurrency and reset the success counter; other 2xx responses
        increment the counter and, when degraded, restore after
        _SUCCESS_THRESHOLD consecutive successes.
        """
        if status in _DEGRADE_STATUSES:
            self._success_counter = 0
            new = max(1, self._current_concurrent // 2)
            self._resize(new)
            return

        if 200 <= status < 300 and self.is_degraded():
            self._success_counter += 1
            if self._success_counter >= _SUCCESS_THRESHOLD:
                self._success_counter = 0
                self._resize(self._base_concurrent)

    def _resize(self, new_concurrent: int) -> None:
        """Swap the internal semaphore for one with a new concurrency budget.

        In-flight permits (acquired by callers currently inside the critical
        section) remain valid against the old semaphore — they'll release into
        a semaphore that no one waits on, which is fine. New waiters will use
        the new semaphore.
        """
        self._current_concurrent = new_concurrent
        self._sem = asyncio.Semaphore(new_concurrent)

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
