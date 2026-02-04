import asyncio

import pytest

from zen_bangumi.scheduler.fallback import AsyncScheduler


@pytest.mark.asyncio
async def test_scheduler_starts_and_stops():
    scheduler = AsyncScheduler()
    
    assert not scheduler.is_running
    assert len(scheduler.tasks) == 0
    
    await scheduler.start()
    
    assert scheduler.is_running
    assert len(scheduler.tasks) == 2
    assert 'rss_refresh' in scheduler.tasks
    assert 'rename' in scheduler.tasks
    
    await scheduler.stop()
    
    assert not scheduler.is_running
    assert len(scheduler.tasks) == 0


@pytest.mark.asyncio
async def test_scheduler_jobs_run_periodically():
    scheduler = AsyncScheduler()
    
    call_count = {'rss': 0, 'rename': 0}
    
    async def mock_rss_job():
        call_count['rss'] += 1
    
    async def mock_rename_job():
        call_count['rename'] += 1
    
    scheduler.rss_refresh_job = mock_rss_job
    scheduler.rename_job = mock_rename_job
    
    await scheduler.start()
    
    await asyncio.sleep(0.1)
    
    await scheduler.stop()
    
    assert call_count['rss'] >= 1
    assert call_count['rename'] >= 1


@pytest.mark.asyncio
async def test_scheduler_handles_job_errors():
    scheduler = AsyncScheduler()
    
    error_count = {'errors': 0}
    
    async def failing_job():
        error_count['errors'] += 1
        raise ValueError("Test error")
    
    scheduler.rss_refresh_job = failing_job
    
    await scheduler.start()
    
    await asyncio.sleep(0.1)
    
    await scheduler.stop()
    
    assert error_count['errors'] >= 1


@pytest.mark.asyncio
async def test_scheduler_graceful_shutdown():
    scheduler = AsyncScheduler()
    
    shutdown_detected = {'value': False}
    
    async def long_running_job():
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            shutdown_detected['value'] = True
            raise
    
    scheduler.rss_refresh_job = long_running_job
    
    await scheduler.start()
    
    await asyncio.sleep(0.1)
    
    await scheduler.stop()
    
    assert shutdown_detected['value']


@pytest.mark.asyncio
async def test_scheduler_double_start_warning():
    scheduler = AsyncScheduler()
    
    await scheduler.start()
    
    await scheduler.start()
    
    assert scheduler.is_running
    
    await scheduler.stop()


@pytest.mark.asyncio
async def test_scheduler_stop_without_start():
    scheduler = AsyncScheduler()
    
    await scheduler.stop()
    
    assert not scheduler.is_running
