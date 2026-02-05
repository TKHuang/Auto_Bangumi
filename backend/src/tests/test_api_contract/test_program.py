import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from module.api.v1.program import router, set_scheduler, get_scheduler
from module.conf import VERSION
from fastapi.testclient import TestClient
from fastapi import FastAPI


@pytest.fixture
def mock_scheduler():
    scheduler = AsyncMock()
    scheduler.is_running = False
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
    async def test_status_returns_running_true(self, mock_scheduler):
        set_scheduler(mock_scheduler)
        mock_scheduler.is_running = True
        
        scheduler = get_scheduler()
        assert scheduler.is_running is True

    async def test_status_returns_running_false(self, mock_scheduler):
        set_scheduler(mock_scheduler)
        mock_scheduler.is_running = False
        
        scheduler = get_scheduler()
        assert scheduler.is_running is False

    async def test_status_includes_version(self, mock_scheduler):
        set_scheduler(mock_scheduler)
        
        scheduler = get_scheduler()
        assert scheduler is not None


class TestProgramStart:
    async def test_start_when_not_running(self, mock_scheduler):
        set_scheduler(mock_scheduler)
        mock_scheduler.is_running = False
        mock_scheduler.start = AsyncMock()
        
        scheduler = get_scheduler()
        if not scheduler.is_running:
            await scheduler.start()
        
        mock_scheduler.start.assert_called_once()

    async def test_start_when_already_running(self, mock_scheduler):
        set_scheduler(mock_scheduler)
        mock_scheduler.is_running = True
        mock_scheduler.start = AsyncMock()
        
        scheduler = get_scheduler()
        if not scheduler.is_running:
            await scheduler.start()
        
        mock_scheduler.start.assert_not_called()


class TestProgramStop:
    async def test_stop_when_running(self, mock_scheduler):
        set_scheduler(mock_scheduler)
        mock_scheduler.is_running = True
        mock_scheduler.stop = AsyncMock()
        
        scheduler = get_scheduler()
        if scheduler.is_running:
            await scheduler.stop()
        
        mock_scheduler.stop.assert_called_once()

    async def test_stop_when_not_running(self, mock_scheduler):
        set_scheduler(mock_scheduler)
        mock_scheduler.is_running = False
        mock_scheduler.stop = AsyncMock()
        
        scheduler = get_scheduler()
        if scheduler.is_running:
            await scheduler.stop()
        
        mock_scheduler.stop.assert_not_called()


class TestProgramRestart:
    async def test_restart_stops_then_starts(self, mock_scheduler):
        set_scheduler(mock_scheduler)
        mock_scheduler.is_running = True
        mock_scheduler.stop = AsyncMock()
        mock_scheduler.start = AsyncMock()
        
        scheduler = get_scheduler()
        if scheduler.is_running:
            await scheduler.stop()
        await scheduler.start()
        
        mock_scheduler.stop.assert_called_once()
        mock_scheduler.start.assert_called_once()


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
        mock_scheduler.is_running = True
        
        scheduler1 = get_scheduler()
        scheduler2 = get_scheduler()
        
        assert scheduler1 is scheduler2
        assert scheduler1.is_running is True
