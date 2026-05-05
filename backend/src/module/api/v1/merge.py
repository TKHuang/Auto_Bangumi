"""/api/v1/bangumi/merge + /api/v1/merge-history/* endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from module.api.middleware.auth import get_current_user
from module.database.engine import get_db_session
from module.repositories.merge_history import BangumiMergeHistoryRepository
from module.services.bangumi_merge import BangumiMergeService

router = APIRouter(tags=["merge"])


def _status_for_merge_error(exc: ValueError) -> int:
    """Map merge-service ValueError messages to HTTP status codes.

    Missing rows → 404; validation/state errors → 400.
    """
    msg = str(exc).lower()
    if "not found" in msg or "missing" in msg:
        return 404
    if "participant was deleted" in msg or "undo unavailable" in msg:
        return 409
    return 400


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class MergeRequest(BaseModel):
    winner_id: int
    loser_id: int
    reason: str = "manual"


class MergeResponse(BaseModel):
    history_id: int
    winner_id: int
    loser_id: int


class MergeHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    winner_bangumi_id: Optional[int]
    loser_bangumi_id: Optional[int]
    merge_reason: str
    merged_at: Optional[str] = None
    merged_by: str
    undone_at: Optional[str] = None
    undone_by: Optional[str] = None


class MergeHistoryList(BaseModel):
    items: list[MergeHistoryItem]
    total: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/bangumi/merge",
    response_model=MergeResponse,
    dependencies=[Depends(get_current_user)],
)
async def merge_bangumi(
    body: MergeRequest,
    session: AsyncSession = Depends(get_db_session),
) -> MergeResponse:
    """Merge `loser_id` into `winner_id` atomically."""
    svc = BangumiMergeService(session)
    try:
        history = await svc.merge(
            winner_id=body.winner_id,
            loser_id=body.loser_id,
            merge_reason=body.reason,
            merged_by="api",
        )
    except ValueError as exc:
        raise HTTPException(status_code=_status_for_merge_error(exc), detail=str(exc))
    await session.commit()
    return MergeResponse(
        history_id=history.id,
        winner_id=body.winner_id,
        loser_id=body.loser_id,
    )


@router.get(
    "/merge-history/",
    response_model=MergeHistoryList,
    dependencies=[Depends(get_current_user)],
)
async def list_merge_history(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
) -> MergeHistoryList:
    """Paginated list of all merge operations, newest first."""
    repo = BangumiMergeHistoryRepository(session)
    rows, total = await repo.list_paginated(limit=limit, offset=offset)
    items = [
        MergeHistoryItem(
            id=h.id,
            winner_bangumi_id=h.winner_bangumi_id,
            loser_bangumi_id=h.loser_bangumi_id,
            merge_reason=h.merge_reason,
            merged_at=h.merged_at.isoformat() if h.merged_at else None,
            merged_by=h.merged_by,
            undone_at=h.undone_at.isoformat() if h.undone_at else None,
            undone_by=h.undone_by,
        )
        for h in rows
    ]
    return MergeHistoryList(items=items, total=total)


@router.post(
    "/merge-history/{history_id}/undo",
    dependencies=[Depends(get_current_user)],
)
async def undo_merge(
    history_id: int,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Reverse a previous merge, resurrecting the loser bangumi (inactive)."""
    svc = BangumiMergeService(session)
    try:
        await svc.undo(history_id=history_id, undone_by="api")
    except ValueError as exc:
        raise HTTPException(status_code=_status_for_merge_error(exc), detail=str(exc))
    await session.commit()
    return {"undone": True, "history_id": history_id}
