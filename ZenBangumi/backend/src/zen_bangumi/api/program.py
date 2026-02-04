from fastapi import APIRouter, Depends, HTTPException, status

from zen_bangumi.api.middleware.auth import get_current_user
from zen_bangumi.api.models import MessageResponse
from zen_bangumi.domain.models.user import User

router = APIRouter(prefix="/api/v1/program", tags=["program"])


@router.post("/start")
async def start_scheduler(current_user: User = Depends(get_current_user)):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Scheduler not yet implemented (Task 21 blocked)",
    )


@router.post("/stop")
async def stop_scheduler(current_user: User = Depends(get_current_user)):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Scheduler not yet implemented (Task 21 blocked)",
    )


@router.post("/restart")
async def restart_scheduler(current_user: User = Depends(get_current_user)):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Scheduler not yet implemented (Task 21 blocked)",
    )


@router.get("/status")
async def get_program_status(current_user: User = Depends(get_current_user)):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Program status not yet implemented (Task 21 blocked)",
    )


@router.post("/shutdown")
async def shutdown_program(current_user: User = Depends(get_current_user)):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Graceful shutdown not yet implemented",
    )


@router.get("/check", response_model=MessageResponse)
async def health_check(current_user: User = Depends(get_current_user)):
    return MessageResponse(message="OK")
