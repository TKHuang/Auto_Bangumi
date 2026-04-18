"""Async rate limiter with max-concurrent + min-interval gating +
dynamic degradation on 429/503 (spec §9.2, §9.3).

State machine:
  - Base state: max_concurrent = base_concurrent
  - 429/503 received: max_concurrent = max(1, max_concurrent // 2)
                      success_counter := 0
  - 10 consecutive 2xx while degraded: max_concurrent = base_concurrent

Used as an async context manager. Not thread-safe; single-worker assumption.

Implementation note: we track in-flight callers with a counter guarded by
an ``asyncio.Condition`` rather than swapping an ``asyncio.Semaphore`` on
resize.  Swapping left stale semaphores around and allowed in-flight
``__aexit__`` releases to land on a fresh semaphore, silently raising the
effective concurrency (review H-3).  The condition-based design lets us
change ``_current_concurrent`` atomically from a synchronous caller and
wake waiters on the next scheduler turn.
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
        self._in_flight = 0
        self._cv = asyncio.Condition()
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
            self._set_concurrent(new)
            return

        if 200 <= status < 300 and self.is_degraded():
            self._success_counter += 1
            if self._success_counter >= _SUCCESS_THRESHOLD:
                self._success_counter = 0
                self._set_concurrent(self._base_concurrent)

    def _set_concurrent(self, new_concurrent: int) -> None:
        """Change the concurrency limit and wake any waiters.

        Safe to call from sync context: schedules a notify coroutine when an
        event loop is running.  If no loop is running we just update the
        counter — waiters, by definition, don't exist in that case.
        """
        self._current_concurrent = new_concurrent
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(self._notify_waiters())

    async def _notify_waiters(self) -> None:
        async with self._cv:
            self._cv.notify_all()

    async def __aenter__(self) -> "RateLimiter":
        async with self._cv:
            while self._in_flight >= self._current_concurrent:
                await self._cv.wait()
            self._in_flight += 1
        try:
            async with self._gate:
                now = time.monotonic()
                wait = self._last_at + self._min_interval - now
                if wait > 0:
                    await asyncio.sleep(wait)
                self._last_at = time.monotonic()
        except BaseException:
            # Roll back the in-flight slot if gating itself fails.
            async with self._cv:
                self._in_flight -= 1
                self._cv.notify()
            raise
        return self

    async def __aexit__(self, *exc) -> None:
        async with self._cv:
            self._in_flight -= 1
            self._cv.notify()
