import pytest
from unittest.mock import AsyncMock

from module.api.v1.program import (
    router,
    set_scheduler,
    get_scheduler,
    _remove_all_schedules,
    _add_all_schedules,
    _has_active_schedules,
)
from fastapi.testclient import TestClient
from fastapi import FastAPI


@pytest.fixture
def mock_scheduler():
    scheduler = AsyncMock()
    scheduler.get_schedule = AsyncMock(return_value=None)
    scheduler.add_schedule = AsyncMock()
    scheduler.remove_schedule = AsyncMock()
    return scheduler


@pytest.fixture
def app_with_scheduler(mock_scheduler):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    set_scheduler(mock_scheduler)
    return app


@pytest.fixture
def client(app_with_scheduler):
    return TestClient(app_with_scheduler)


class TestProgramStatus:
    async def test_status_true_when_schedules_exist(self, mock_scheduler):
        set_scheduler(mock_scheduler)
        mock_scheduler.get_schedule = AsyncMock(return_value="some_schedule")

        assert await _has_active_schedules() is True

    async def test_status_false_when_no_schedules(self, mock_scheduler):
        set_scheduler(mock_scheduler)
        mock_scheduler.get_schedule = AsyncMock(return_value=None)

        assert await _has_active_schedules() is False


class TestProgramStop:
    async def test_stop_removes_all_schedules(self, mock_scheduler):
        set_scheduler(mock_scheduler)

        await _remove_all_schedules()

        assert mock_scheduler.remove_schedule.call_count == 3
        mock_scheduler.remove_schedule.assert_any_call("rename")
        mock_scheduler.remove_schedule.assert_any_call("rss_refresh")
        mock_scheduler.remove_schedule.assert_any_call("enrichment_retry")

    async def test_stop_ignores_missing_schedules(self, mock_scheduler):
        set_scheduler(mock_scheduler)
        from apscheduler import ScheduleLookupError

        mock_scheduler.remove_schedule = AsyncMock(side_effect=ScheduleLookupError("x"))

        await _remove_all_schedules()


class TestProgramStart:
    async def test_start_adds_all_schedules(self, mock_scheduler):
        set_scheduler(mock_scheduler)

        await _add_all_schedules()

        assert mock_scheduler.add_schedule.call_count == 3

    async def test_start_idempotent_when_already_active(self, mock_scheduler):
        set_scheduler(mock_scheduler)
        mock_scheduler.get_schedule = AsyncMock(return_value="exists")

        has = await _has_active_schedules()
        assert has is True


class TestProgramRestart:
    async def test_restart_removes_then_adds(self, mock_scheduler):
        set_scheduler(mock_scheduler)

        await _remove_all_schedules()
        await _add_all_schedules()

        assert mock_scheduler.remove_schedule.call_count == 3
        assert mock_scheduler.add_schedule.call_count == 3


class TestSchedulerNotInitialized:
    def test_get_scheduler_raises_when_not_set(self):
        from module.api.v1 import program as program_module
        program_module._scheduler = None

        with pytest.raises(RuntimeError, match="Scheduler not initialized"):
            get_scheduler()


class TestSchedulerIntegration:
    async def test_set_and_get_scheduler(self, mock_scheduler):
        set_scheduler(mock_scheduler)
        retrieved = get_scheduler()
        assert retrieved is mock_scheduler

    async def test_scheduler_state_persistence(self, mock_scheduler):
        set_scheduler(mock_scheduler)

        scheduler1 = get_scheduler()
        scheduler2 = get_scheduler()

        assert scheduler1 is scheduler2
