"""Config API endpoints."""
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from module.api.middleware.auth import get_current_user
from module.conf import settings
from module.conf.models import Config

router = APIRouter(prefix="/config", tags=["config"])

logger = logging.getLogger(__name__)


@router.get("/get", response_model=Config, dependencies=[Depends(get_current_user)])
async def get_config():
    """Get full configuration.
    
    Returns complete Config object with all settings.
    Requires valid authentication token.
    """
    return settings


async def _reschedule_jobs_with_current_config() -> None:
    """Re-add the recurring jobs so newly persisted intervals take effect.

    APScheduler's ``IntervalTrigger`` is fixed at schedule-creation time, so
    bumping ``program.rss_time`` / ``program.rename_time`` /
    ``program.enrichment_retry_time`` only sticks if we drop and re-add the
    schedules. Without this the user changes the slider in the UI, hits Save,
    sees a green toast, and the cron keeps firing on the old cadence until
    they manually press "Restart" — which is the bug we're fixing.

    The reschedule is best-effort: if the scheduler isn't initialised yet
    (e.g. test harness without lifespan) we simply skip it.
    """
    try:
        from module.api.v1.program import (
            _add_all_schedules,
            _has_active_schedules,
            _remove_all_schedules,
            get_scheduler,
        )

        get_scheduler()  # Raise RuntimeError if scheduler missing.
        if not await _has_active_schedules():
            logger.info(
                "Scheduler has no active schedules; preserving stopped state after config update"
            )
            return

        await _remove_all_schedules()
        await _add_all_schedules()
        logger.info(
            "Re-applied schedules after config update: rename %ds, rss %ds, enrichment %ds",
            settings.program.rename_time,
            settings.program.rss_time,
            settings.program.enrichment_retry_time,
        )
    except RuntimeError:
        logger.debug("Scheduler not initialised; skipping reschedule")
    except Exception:
        # Reschedule failure should not roll back the saved config — surface
        # a warning and let the user click Restart explicitly if needed.
        logger.exception("Failed to apply new schedule intervals after config update")


@router.patch("/update", dependencies=[Depends(get_current_user)])
async def update_config(config: Config):
    """Update configuration and persist to JSON file.
    
    Accepts complete Config object and saves to config.json.
    Returns success/failure message in both English and Chinese.
    Requires valid authentication token.
    """
    try:
        settings.save(config_dict=config.model_dump(by_alias=True))
        settings.load()
        await _reschedule_jobs_with_current_config()

        return JSONResponse(
            status_code=200,
            content={
                "msg_en": "Update config successfully.",
                "msg_zh": "更新配置成功。",
            },
        )
    except Exception as e:
        logger.error(f"Config update failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "msg_en": "Update config failed.",
                "msg_zh": "更新配置失败。",
            },
        )
