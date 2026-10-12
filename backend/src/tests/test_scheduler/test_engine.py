import pytest

from module.scheduler.engine import AsyncScheduler, create_scheduler


async def _test_job():
    pass


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


class TestAsyncSchedulerEdgeCases:
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
