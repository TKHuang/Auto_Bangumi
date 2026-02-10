"""Config API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from module.api.middleware.auth import get_current_user
from module.conf import settings
from module.conf.models import Config

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/get", response_model=Config, dependencies=[Depends(get_current_user)])
async def get_config():
    """Get full configuration.
    
    Returns complete Config object with all settings.
    Requires valid authentication token.
    """
    return settings


@router.patch("/update", dependencies=[Depends(get_current_user)])
async def update_config(config: Config):
    """Update configuration and persist to JSON file.
    
    Accepts complete Config object and saves to config.json.
    Returns success/failure message in both English and Chinese.
    Requires valid authentication token.
    """
    try:
        # Save config to JSON file
        settings.save(config_dict=config.model_dump(by_alias=True))
        # Reload settings from file
        settings.load()
        
        return JSONResponse(
            status_code=200,
            content={
                "msg_en": "Update config successfully.",
                "msg_zh": "更新配置成功。",
            },
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Config update failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "msg_en": "Update config failed.",
                "msg_zh": "更新配置失败。",
            },
        )
