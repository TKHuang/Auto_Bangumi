"""Program control endpoints.

The APScheduler process is managed solely by the app lifespan (main.py).
These endpoints control scheduled jobs by adding/removing schedules,
NOT by stopping/starting the scheduler process itself.
This avoids anyio cancel-scope task-affinity errors.
"""
from __future__ import annotations

import logging
import os
import signal
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from module.conf import VERSION, settings
from module.api.middleware.auth import get_current_user
from module.scheduler.jobs.enrichment_retry import enrichment_retry_job
from module.scheduler.jobs.rename import rename_job
from module.scheduler.jobs.rss_refresh import rss_refresh_job

if TYPE_CHECKING:
    from module.scheduler import AsyncScheduler

logger = logging.getLogger(__name__)
router = APIRouter(tags=["program"])

# Global scheduler instance - will be set by main.py
_scheduler: AsyncScheduler | None = None

_SCHEDULE_IDS = ["rename", "rss_refresh", "enrichment_retry"]


def set_scheduler(scheduler: AsyncScheduler) -> None:
    """Set the global scheduler instance."""
    global _scheduler
    _scheduler = scheduler


def get_scheduler() -> AsyncScheduler:
    """Get the global scheduler instance."""
    if _scheduler is None:
        raise RuntimeError("Scheduler not initialized")
    return _scheduler


async def _remove_all_schedules() -> None:
    """Remove all known schedules (ignore if already absent)."""
    scheduler = get_scheduler()
    for sid in _SCHEDULE_IDS:
        try:
            await scheduler.remove_schedule(sid)
        except Exception:
            pass


async def _add_all_schedules() -> None:
    """Add all schedules with current config values."""
    scheduler = get_scheduler()
    await scheduler.add_schedule(
        rename_job,
        trigger="interval",
        id="rename",
        seconds=settings.program.rename_time,
    )
    await scheduler.add_schedule(
        rss_refresh_job,
        trigger="interval",
        id="rss_refresh",
        seconds=settings.program.rss_time,
    )
    await scheduler.add_schedule(
        enrichment_retry_job,
        trigger="interval",
        id="enrichment_retry",
        seconds=settings.program.enrichment_retry_time,
    )


async def _has_active_schedules() -> bool:
    """Check whether any known schedules are registered."""
    scheduler = get_scheduler()
    for sid in _SCHEDULE_IDS:
        if await scheduler.get_schedule(sid) is not None:
            return True
    return False


@router.post("/restart", dependencies=[Depends(get_current_user)])
async def restart():
    """Restart scheduled jobs with current config (does not restart the process)."""
    try:
        await _remove_all_schedules()
        await _add_all_schedules()
        logger.info(
            f"Schedules restarted: rename ({settings.program.rename_time}s), "
            f"rss_refresh ({settings.program.rss_time}s), "
            f"enrichment_retry ({settings.program.enrichment_retry_time}s)"
        )
        return {
            "msg_en": "Program restarted successfully.",
            "msg_zh": "程序重启成功。",
        }
    except Exception as e:
        logger.debug(e)
        logger.warning("Failed to restart program")
        raise HTTPException(
            status_code=500,
            detail={
                "msg_en": "Failed to restart program.",
                "msg_zh": "重启程序失败。",
            },
        )


@router.post("/start", dependencies=[Depends(get_current_user)])
async def start():
    """Re-add scheduled jobs (resume after stop)."""
    try:
        if await _has_active_schedules():
            return {
                "msg_en": "Program started successfully.",
                "msg_zh": "程序启动成功。",
            }
        await _add_all_schedules()
        logger.info("Schedules started")
        return {
            "msg_en": "Program started successfully.",
            "msg_zh": "程序启动成功。",
        }
    except Exception as e:
        logger.debug(e)
        logger.warning("Failed to start program")
        raise HTTPException(
            status_code=500,
            detail={
                "msg_en": "Failed to start program.",
                "msg_zh": "启动程序失败。",
            },
        )


@router.post("/stop", dependencies=[Depends(get_current_user)])
async def stop():
    """Remove all scheduled jobs (pause without killing the process)."""
    try:
        await _remove_all_schedules()
        logger.info("Schedules stopped")
        return {
            "msg_en": "Program stopped successfully.",
            "msg_zh": "程序停止成功。",
        }
    except Exception as e:
        logger.debug(e)
        logger.warning("Failed to stop program")
        raise HTTPException(
            status_code=500,
            detail={
                "msg_en": "Failed to stop program.",
                "msg_zh": "停止程序失败。",
            },
        )


@router.get("/health")
async def health():
    """Unauthenticated health check for Docker healthcheck."""
    return {"status": "ok"}


@router.get("/status", dependencies=[Depends(get_current_user)])
async def program_status():
    """Get program status."""
    try:
        has_jobs = await _has_active_schedules()
        return {
            "status": has_jobs,
            "version": VERSION,
        }
    except Exception:
        return {
            "status": False,
            "version": VERSION,
        }


@router.post("/shutdown", dependencies=[Depends(get_current_user)])
async def shutdown_program():
    """Gracefully shutdown the program."""
    try:
        scheduler = get_scheduler()
        if scheduler.is_running:
            await scheduler.stop()
    except Exception as e:
        logger.debug(e)
    
    logger.info("Shutting down program...")
    os.kill(os.getpid(), signal.SIGINT)
    return JSONResponse(
        status_code=200,
        content={
            "msg_en": "Shutdown program successfully.",
            "msg_zh": "关闭程序成功。",
        },
    )
