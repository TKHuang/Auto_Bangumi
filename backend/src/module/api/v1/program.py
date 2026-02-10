"""Program control endpoints."""
from __future__ import annotations

import logging
import os
import signal
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from module.conf import VERSION
from module.api.middleware.auth import get_current_user

if TYPE_CHECKING:
    from module.scheduler import AsyncScheduler

logger = logging.getLogger(__name__)
router = APIRouter(tags=["program"])

# Global scheduler instance - will be set by main.py
_scheduler: AsyncScheduler | None = None


def set_scheduler(scheduler: AsyncScheduler) -> None:
    """Set the global scheduler instance."""
    global _scheduler
    _scheduler = scheduler


def get_scheduler() -> AsyncScheduler:
    """Get the global scheduler instance."""
    if _scheduler is None:
        raise RuntimeError("Scheduler not initialized")
    return _scheduler


@router.post("/restart", dependencies=[Depends(get_current_user)])
async def restart():
    """Restart the scheduler."""
    try:
        scheduler = get_scheduler()
        if scheduler.is_running:
            await scheduler.stop()
        await scheduler.start()
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
    """Start the scheduler."""
    try:
        scheduler = get_scheduler()
        if not scheduler.is_running:
            await scheduler.start()
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
    """Stop the scheduler."""
    try:
        scheduler = get_scheduler()
        if scheduler.is_running:
            await scheduler.stop()
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
        scheduler = get_scheduler()
        return {
            "status": scheduler.is_running,
            "version": VERSION,
        }
    except Exception as e:
        logger.debug(e)
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
