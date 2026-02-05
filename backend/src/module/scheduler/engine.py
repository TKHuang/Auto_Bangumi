from __future__ import annotations

import asyncio
import logging
from contextlib import AsyncExitStack
from typing import Any, Callable

from apscheduler import AsyncScheduler as APAsyncScheduler, ConflictPolicy, ScheduleLookupError  # type: ignore[import-not-found]
from apscheduler.datastores.memory import MemoryDataStore  # type: ignore[import-not-found]
from apscheduler.triggers.interval import IntervalTrigger  # type: ignore[import-not-found]

logger = logging.getLogger(__name__)


class AsyncScheduler:
    def __init__(self, data_store: MemoryDataStore | None = None):
        self.data_store = data_store or MemoryDataStore()
        self._scheduler: APAsyncScheduler | None = None
        self._started = False
        self._exit_stack: AsyncExitStack | None = None

    async def __aenter__(self) -> AsyncScheduler:
        await self.start()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.stop()

    async def start(self) -> None:
        if self._started:
            logger.warning("Scheduler already started")
            return

        self._exit_stack = AsyncExitStack()
        await self._exit_stack.__aenter__()

        self._scheduler = APAsyncScheduler(data_store=self.data_store)
        await self._exit_stack.enter_async_context(self._scheduler)  # type: ignore[arg-type]
        await self._scheduler.start_in_background()  # type: ignore[attr-defined]
        self._started = True
        logger.info("Scheduler started")

    async def stop(self) -> None:
        if not self._started or self._scheduler is None:
            logger.warning("Scheduler not started")
            return

        if self._exit_stack is not None:
            await self._exit_stack.__aexit__(None, None, None)

        self._started = False
        logger.info("Scheduler stopped")

    @property
    def is_running(self) -> bool:
        return self._started and self._scheduler is not None

    async def add_schedule(
        self,
        func: Callable[..., Any],
        trigger: str | IntervalTrigger = "interval",
        id: str | None = None,
        conflict_policy: str | ConflictPolicy = ConflictPolicy.do_nothing,
        max_running_jobs: int | None = None,
        **trigger_args: Any,
    ) -> Any:
        if not self._started or self._scheduler is None:
            raise RuntimeError("Scheduler not started")

        if isinstance(trigger, str):
            if trigger == "interval":
                if "seconds" in trigger_args and trigger_args["seconds"] <= 0:
                    raise ValueError("Interval must be positive")
                trigger_obj = IntervalTrigger(**trigger_args)
            else:
                raise ValueError(f"Unsupported trigger type: {trigger}")
        else:
            trigger_obj = trigger

        if isinstance(conflict_policy, str):
            conflict_policy = ConflictPolicy[conflict_policy.lower()]

        schedule_id = await self._scheduler.add_schedule(
            func,
            trigger_obj,
            id=id,
            conflict_policy=conflict_policy,
        )
        return await self._scheduler.get_schedule(schedule_id)

    async def remove_schedule(self, job_id: str) -> None:
        if not self._started or self._scheduler is None:
            raise RuntimeError("Scheduler not started")

        await self._scheduler.remove_schedule(job_id)

    async def get_schedule(self, job_id: str) -> Any:
        if not self._started or self._scheduler is None:
            raise RuntimeError("Scheduler not started")

        try:
            return await self._scheduler.get_schedule(job_id)
        except ScheduleLookupError:
            return None


def create_scheduler() -> AsyncScheduler:
    return AsyncScheduler(data_store=MemoryDataStore())
