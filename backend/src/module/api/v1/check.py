"""Health check API endpoints."""
from fastapi import APIRouter, Depends

from module.api.middleware.auth import get_current_user
from module.conf import settings
from module.services.downloader.factory import create_downloader

router = APIRouter(prefix="/check", tags=["check"])


@router.get("/downloader", dependencies=[Depends(get_current_user)])
async def check_downloader() -> bool:
    """Check if configured downloader is reachable and can authenticate."""
    try:
        downloader = create_downloader(settings)
        if not await downloader.check_host():
            return False
        if not await downloader.auth():
            return False
        return True
    except Exception:
        return False
