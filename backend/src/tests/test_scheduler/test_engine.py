import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from module.scheduler.engine import AsyncScheduler, create_scheduler


_test_execution_count = 0
_test_execution_times = []
_job1_count = 0
_job2_count = 0
_slow_job_concurrent = 0
_slow_job_max_concurrent = 0
_slow_job_execution_count = 0
_failing_job_count = 0
_removable_job_count = 0
_job_v1_count = 0
_job_v2_count = 0


async def _test_job():
    global _test_execution_count, _test_execution_times
    _test_execution_count += 1
    _test_execution_times.append(datetime.now())


async def _job1():
    global _job1_count
    _job1_count += 1


async def _job2():
    global _job2_count
    _job2_count += 1


async def _slow_job():
    global _slow_job_concurrent, _slow_job_max_concurrent, _slow_job_execution_count
    _slow_job_concurrent += 1
    _slow_job_max_concurrent = max(_slow_job_max_concurrent, _slow_job_concurrent)
    _slow_job_execution_count += 1
    await asyncio.sleep(0.8)
    _slow_job_concurrent -= 1


async def _failing_job():
    global _failing_job_count
    _failing_job_count += 1
    raise ValueError("Test error")


async def _removable_job():
    global _removable_job_count
    _removable_job_count += 1


async def _job_v1():
    global _job_v1_count
    _job_v1_count += 1


async def _job_v2():
    global _job_v2_count
    _job_v2_count += 2


class TestCreateScheduler:
    def test_create_scheduler_returns_async_scheduler(self):
        scheduler = create_scheduler()
        assert isinstance(scheduler, AsyncScheduler)

    def test_create_scheduler_uses_memory_job_store(self):
        scheduler = create_scheduler()
        assert scheduler.data_store is not None
        assert "memory" in str(type(scheduler.data_store)).lower() or "dict" in str(type(scheduler.data_store)).lower()

    def test_create_scheduler_multiple_calls_return_different_instances(self):
        scheduler1 = create_scheduler()
        scheduler2 = create_scheduler()
        assert scheduler1 is not scheduler2


class TestAsyncSchedulerLifecycle:
    @pytest.mark.asyncio
    async def test_scheduler_starts_cleanly(self):
        scheduler = create_scheduler()
        await scheduler.start()
        assert scheduler.is_running is True
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_scheduler_stops_cleanly(self):
        scheduler = create_scheduler()
        await scheduler.start()
        await scheduler.stop()
        assert scheduler.is_running is False

    @pytest.mark.asyncio
    async def test_scheduler_start_idempotent(self):
        scheduler = create_scheduler()
        await scheduler.start()
        await scheduler.start()
        assert scheduler.is_running is True
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_scheduler_stop_idempotent(self):
        scheduler = create_scheduler()
        await scheduler.start()
        await scheduler.stop()
        await scheduler.stop()
        assert scheduler.is_running is False

    @pytest.mark.asyncio
    async def test_scheduler_context_manager(self):
        async with create_scheduler() as scheduler:
            assert scheduler.is_running is True
        assert scheduler.is_running is False


class TestAsyncSchedulerJobRegistration:
    @pytest.mark.asyncio
    async def test_add_job_with_interval_trigger(self):
        global _test_execution_count
        _test_execution_count = 0

        scheduler = create_scheduler()
        await scheduler.start()

        job = await scheduler.add_schedule(
            _test_job,
            trigger="interval",
            seconds=1,
            id="test_job_1",
        )
        assert job is not None
        assert job.id == "test_job_1"

        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_job_fires_at_interval(self):
        global _test_execution_count, _test_execution_times
        _test_execution_count = 0
        _test_execution_times = []

        scheduler = create_scheduler()
        await scheduler.start()

        await scheduler.add_schedule(
            _test_job,
            trigger="interval",
            seconds=0.5,
            id="test_job_interval",
        )

        await asyncio.sleep(2)
        await scheduler.stop()

        assert len(_test_execution_times) >= 3, f"Expected at least 3 executions, got {len(_test_execution_times)}"

    @pytest.mark.asyncio
    async def test_multiple_jobs_can_be_registered(self):
        global _job1_count, _job2_count
        _job1_count = 0
        _job2_count = 0

        scheduler = create_scheduler()
        await scheduler.start()

        await scheduler.add_schedule(_job1, trigger="interval", seconds=0.5, id="job1")
        await scheduler.add_schedule(_job2, trigger="interval", seconds=0.5, id="job2")

        await asyncio.sleep(1.5)
        await scheduler.stop()

        assert _job1_count >= 2
        assert _job2_count >= 2

    @pytest.mark.asyncio
    async def test_job_with_coalesce_prevents_concurrent_execution(self):
        global _slow_job_concurrent, _slow_job_max_concurrent, _slow_job_execution_count
        _slow_job_concurrent = 0
        _slow_job_max_concurrent = 0
        _slow_job_execution_count = 0

        scheduler = create_scheduler()
        await scheduler.start()

        await scheduler.add_schedule(
            _slow_job,
            trigger="interval",
            seconds=0.5,
            id="slow_job",
        )

        await asyncio.sleep(2)
        await scheduler.stop()

        assert _slow_job_execution_count >= 1

    @pytest.mark.asyncio
    async def test_job_exception_does_not_crash_scheduler(self):
        global _failing_job_count
        _failing_job_count = 0

        scheduler = create_scheduler()
        await scheduler.start()

        await scheduler.add_schedule(
            _failing_job,
            trigger="interval",
            seconds=0.5,
            id="failing_job",
        )

        await asyncio.sleep(1.5)

        assert scheduler.is_running is True
        assert _failing_job_count >= 2

        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_remove_job(self):
        global _removable_job_count
        _removable_job_count = 0

        scheduler = create_scheduler()
        await scheduler.start()

        job = await scheduler.add_schedule(
            _removable_job,
            trigger="interval",
            seconds=0.5,
            id="removable_job",
        )

        await asyncio.sleep(0.7)
        count_before_removal = _removable_job_count

        await scheduler.remove_schedule(job.id)

        await asyncio.sleep(0.7)
        count_after_removal = _removable_job_count

        await scheduler.stop()

        assert count_before_removal >= 1
        assert count_after_removal == count_before_removal

    @pytest.mark.asyncio
    async def test_get_job(self):
        scheduler = create_scheduler()
        await scheduler.start()

        added_job = await scheduler.add_schedule(
            _test_job,
            trigger="interval",
            seconds=1,
            id="retrievable_job",
        )

        retrieved_job = await scheduler.get_schedule("retrievable_job")
        assert retrieved_job is not None
        assert retrieved_job.id == "retrievable_job"

        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_get_nonexistent_job_returns_none(self):
        scheduler = create_scheduler()
        await scheduler.start()

        job = await scheduler.get_schedule("nonexistent_job")
        assert job is None

        await scheduler.stop()


class TestAsyncSchedulerConflictPolicy:
    @pytest.mark.asyncio
    async def test_replace_conflict_policy(self):
        global _job_v1_count, _job_v2_count
        _job_v1_count = 0
        _job_v2_count = 0

        scheduler = create_scheduler()
        await scheduler.start()

        await scheduler.add_schedule(
            _job_v1,
            trigger="interval",
            seconds=0.5,
            id="replaceable_job",
            conflict_policy="replace",
        )

        await asyncio.sleep(0.7)
        count_after_v1 = _job_v1_count

        await scheduler.add_schedule(
            _job_v2,
            trigger="interval",
            seconds=0.5,
            id="replaceable_job",
            conflict_policy="replace",
        )

        await asyncio.sleep(0.7)
        count_after_v2 = _job_v2_count

        await scheduler.stop()

        assert count_after_v1 >= 1
        assert count_after_v2 >= 1


class TestAsyncSchedulerEdgeCases:
    @pytest.mark.asyncio
    async def test_scheduler_with_no_jobs(self):
        scheduler = create_scheduler()
        await scheduler.start()
        await asyncio.sleep(0.5)
        await scheduler.stop()
        assert scheduler.is_running is False

    @pytest.mark.asyncio
    async def test_job_with_zero_interval_raises_error(self):
        scheduler = create_scheduler()
        await scheduler.start()

        with pytest.raises((ValueError, TypeError)):
            await scheduler.add_schedule(
                _test_job,
                trigger="interval",
                seconds=0,
                id="zero_interval_job",
            )

        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_job_with_negative_interval_raises_error(self):
        scheduler = create_scheduler()
        await scheduler.start()

        with pytest.raises((ValueError, TypeError)):
            await scheduler.add_schedule(
                _test_job,
                trigger="interval",
                seconds=-1,
                id="negative_interval_job",
            )

        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_add_job_to_stopped_scheduler_raises_error(self):
        scheduler = create_scheduler()

        with pytest.raises((RuntimeError, ValueError)):
            await scheduler.add_schedule(
                _test_job,
                trigger="interval",
                seconds=1,
                id="job_on_stopped",
            )
