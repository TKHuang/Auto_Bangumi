from pathlib import Path

from fastapi import APIRouter, Depends

from zen_bangumi.api.middleware.auth import get_current_user
from zen_bangumi.api.models import MessageResponse
from zen_bangumi.domain.models.user import User

router = APIRouter(prefix="/api/v1/log", tags=["log"])


@router.get("/")
async def get_logs(current_user: User = Depends(get_current_user)):
    log_file = Path("data/log.txt")
    if not log_file.exists():
        return {"logs": ""}
    
    with open(log_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
        last_1000 = lines[-1000:]
        return {"logs": "".join(last_1000)}


@router.delete("/", response_model=MessageResponse)
async def clear_logs(current_user: User = Depends(get_current_user)):
    log_file = Path("data/log.txt")
    if log_file.exists():
        log_file.write_text("", encoding="utf-8")
    
    return MessageResponse(message="Log file cleared successfully")
