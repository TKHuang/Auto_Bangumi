"""RssLockRegistry tests (spec §9.1)."""
import asyncio

import pytest

from module.concurrency.rss_lock import RssLockRegistry


@pytest.mark.unit
class TestRssLockRegistry:
    async def test_first_acquire_returns_lock(self):
        registry = RssLockRegistry()
        lock = await registry.try_acquire(rss_id=1)
        assert lock is not None
        lock.release()

    async def test_second_acquire_while_held_returns_none(self):
        registry = RssLockRegistry()
        first = await registry.try_acquire(rss_id=1)
        assert first is not None

        second = await registry.try_acquire(rss_id=1)
        assert second is None

        first.release()

    async def test_acquire_returns_lock_after_release(self):
        registry = RssLockRegistry()
        first = await registry.try_acquire(rss_id=1)
        first.release()

        second = await registry.try_acquire(rss_id=1)
        assert second is not None
        second.release()

    async def test_different_rss_ids_are_independent(self):
        registry = RssLockRegistry()
        a = await registry.try_acquire(rss_id=1)
        b = await registry.try_acquire(rss_id=2)
        assert a is not None
        assert b is not None
        a.release()
        b.release()

    async def test_concurrent_acquire_only_one_wins(self):
        """Under concurrent try_acquire on the same rss_id, exactly one wins."""
        registry = RssLockRegistry()

        async def attempt() -> bool:
            lock = await registry.try_acquire(rss_id=42)
            if lock is None:
                return False
            await asyncio.sleep(0.01)
            lock.release()
            return True

        results = await asyncio.gather(*(attempt() for _ in range(5)))
        # Exactly one of the five attempts should win.
        assert sum(results) == 1
