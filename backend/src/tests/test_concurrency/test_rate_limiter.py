"""RateLimiter unit tests (base behavior, spec §9.2)."""
import asyncio
import time

import pytest

from module.concurrency.rate_limiter import RateLimiter


@pytest.mark.unit
class TestRateLimiterConcurrency:
    async def test_respects_max_concurrent(self):
        """At most max_concurrent entries into the critical section at once."""
        rl = RateLimiter(max_concurrent=2, min_interval_ms=0)
        in_flight = 0
        peak = 0

        async def worker():
            nonlocal in_flight, peak
            async with rl:
                in_flight += 1
                peak = max(peak, in_flight)
                await asyncio.sleep(0.05)
                in_flight -= 1

        await asyncio.gather(*(worker() for _ in range(6)))
        assert peak == 2

    async def test_respects_min_interval(self):
        """Successive calls are spaced by >= min_interval_ms."""
        rl = RateLimiter(max_concurrent=1, min_interval_ms=50)
        timestamps: list[float] = []

        async def worker():
            async with rl:
                timestamps.append(time.monotonic())

        for _ in range(3):
            await worker()

        gaps = [timestamps[i + 1] - timestamps[i] for i in range(len(timestamps) - 1)]
        assert all(g >= 0.045 for g in gaps), f"gaps too tight: {gaps}"


@pytest.mark.unit
class TestRateLimiterReleasesOnException:
    async def test_releases_semaphore_on_exception(self):
        rl = RateLimiter(max_concurrent=1, min_interval_ms=0)

        with pytest.raises(ValueError):
            async with rl:
                raise ValueError("oops")

        # Should still be acquirable afterwards — not deadlocked.
        async with asyncio.timeout(1):
            async with rl:
                pass


@pytest.mark.unit
class TestRateLimiterDegradation:
    async def test_429_halves_concurrent(self):
        rl = RateLimiter(max_concurrent=4, min_interval_ms=0)
        assert rl.current_concurrent() == 4
        rl.record_result(status=429)
        assert rl.current_concurrent() == 2

    async def test_503_halves_concurrent(self):
        rl = RateLimiter(max_concurrent=4, min_interval_ms=0)
        rl.record_result(status=503)
        assert rl.current_concurrent() == 2

    async def test_halving_floors_at_one(self):
        rl = RateLimiter(max_concurrent=2, min_interval_ms=0)
        rl.record_result(status=429)
        assert rl.current_concurrent() == 1
        rl.record_result(status=429)
        assert rl.current_concurrent() == 1  # does not go below 1

    async def test_ten_consecutive_successes_restore(self):
        rl = RateLimiter(max_concurrent=4, min_interval_ms=0)
        rl.record_result(status=503)
        assert rl.current_concurrent() == 2

        for _ in range(9):
            rl.record_result(status=200)
        assert rl.current_concurrent() == 2  # not yet

        rl.record_result(status=200)
        assert rl.current_concurrent() == 4  # 10th success restores

    async def test_failure_between_successes_resets_counter(self):
        rl = RateLimiter(max_concurrent=4, min_interval_ms=0)
        rl.record_result(status=503)
        for _ in range(5):
            rl.record_result(status=200)
        rl.record_result(status=503)  # resets success counter
        for _ in range(5):
            rl.record_result(status=200)
        # Only 5 successes since last failure — still degraded
        assert rl.current_concurrent() == 1  # halved twice: 4 -> 2 -> 1

    async def test_is_degraded_flag(self):
        rl = RateLimiter(max_concurrent=4, min_interval_ms=0)
        assert rl.is_degraded() is False
        rl.record_result(status=429)
        assert rl.is_degraded() is True

        for _ in range(10):
            rl.record_result(status=200)
        assert rl.is_degraded() is False
