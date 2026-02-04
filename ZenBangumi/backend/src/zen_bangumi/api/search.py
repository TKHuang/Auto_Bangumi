from fastapi import APIRouter, Depends, HTTPException, status

from zen_bangumi.api.middleware.auth import get_current_user
from zen_bangumi.domain.models.user import User

router = APIRouter(prefix="/api/v1/search", tags=["search"])


@router.get("/providers")
async def list_providers(current_user: User = Depends(get_current_user)):
    return {"providers": ["mikan"]}


@router.get("/{keyword}")
async def search_anime(
    keyword: str,
    current_user: User = Depends(get_current_user),
):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented - waiting for Task 20 (Search System)",
    )
