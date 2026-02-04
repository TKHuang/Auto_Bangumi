"""Asyncio-based fallback scheduler for background tasks.

This module provides a simple asyncio-based scheduler as a fallback
since APScheduler 4.x is not available. It runs periodic jobs in the
background using asyncio.create_task().
"""

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any, Callable

logger = logging.getLogger(__name__)


class AsyncScheduler:
    """Asyncio-based background task scheduler.
    
    Manages periodic background jobs using asyncio tasks. Supports
    graceful shutdown and error handling for individual jobs.
    
    Example:
        scheduler = AsyncScheduler()
        await scheduler.start()
        # ... application runs ...
        await scheduler.stop()
    """
    
    def __init__(self):
        """Initialize the scheduler."""
        self.tasks: dict[str, asyncio.Task[None]] = {}
        self.shutdown_event: asyncio.Event = asyncio.Event()
        self._started: bool = False
        
    async def start(self):
        """Start all background jobs.
        
        Creates asyncio tasks for RSS refresh and rename jobs.
        Jobs run periodically until shutdown is requested.
        """
        if self._started:
            logger.warning("Scheduler already started")
            return
            
        logger.info("Starting background scheduler...")
        self.shutdown_event.clear()
        
        # Start RSS refresh job (every 15 minutes)
        self.tasks['rss_refresh'] = asyncio.create_task(
            self._run_periodic(
                self.rss_refresh_job,
                interval=900,
                name="RSS Refresh"
            )
        )
        
        # Start rename job (every 1 minute)
        self.tasks['rename'] = asyncio.create_task(
            self._run_periodic(
                self.rename_job,
                interval=60,
                name="Rename"
            )
        )
        
        self._started = True
        logger.info(f"Scheduler started with {len(self.tasks)} jobs")
        
    async def _run_periodic(
        self,
        job_func: Callable[[], Coroutine[Any, Any, None]],
        interval: int,
        name: str
    ) -> None:
        """Run a job periodically until shutdown.
        
        Args:
            job_func: Async function to run periodically
            interval: Seconds between job executions
            name: Human-readable job name for logging
        """
        logger.info(f"Starting periodic job: {name} (interval={interval}s)")
        
        while not self.shutdown_event.is_set():
            try:
                await job_func()
            except Exception as e:
                logger.error(f"Error in {name} job: {e}", exc_info=True)
            
            # Sleep with cancellation support
            try:
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                logger.info(f"Job {name} cancelled during sleep")
                break
                
        logger.info(f"Periodic job stopped: {name}")
        
    async def rss_refresh_job(self):
        """RSS refresh background job (placeholder).
        
        This is a placeholder that will be implemented when Task 18
        (RSS refresh service) is completed.
        """
        logger.debug("RSS refresh job executed (not implemented)")
        
    async def rename_job(self):
        """Rename background job (placeholder).
        
        This is a placeholder that will be implemented when Task 17
        (rename service) is completed.
        """
        logger.debug("Rename job executed (not implemented)")
        
    async def stop(self):
        """Stop all background jobs gracefully.
        
        Sets shutdown event and cancels all running tasks.
        Waits for tasks to complete with exception handling.
        """
        if not self._started:
            logger.warning("Scheduler not started")
            return
            
        logger.info("Stopping background scheduler...")
        self.shutdown_event.set()
        
        # Cancel all tasks
        for name, task in self.tasks.items():
            if not task.done():
                logger.debug(f"Cancelling task: {name}")
                _ = task.cancel()
        
        # Wait for all tasks to complete
        if self.tasks:
            _ = await asyncio.gather(*self.tasks.values(), return_exceptions=True)
            
        self.tasks.clear()
        self._started = False
        logger.info("Scheduler stopped")
        
    @property
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._started and not self.shutdown_event.is_set()
