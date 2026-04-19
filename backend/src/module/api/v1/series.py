"""/api/v1/series/* endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from module.api.middleware.auth import get_current_user
from module.database.engine import get_db_session
from module.repositories.series import SeriesRepository

router = APIRouter(prefix="/series", tags=["series"])


class SeriesOut(BaseModel):
    id: int
    canonical_title: str
    normalized_title: str
    season: int
    cour_part: Optional[str] = None
    year: Optional[int] = None
    root_path: str
    poster_url: Optional[str] = None
    default_filter: Optional[str] = None
    default_offset: Optional[int] = None
    pending_review: bool

    model_config = ConfigDict(from_attributes=True)


class SeriesListOut(BaseModel):
    items: list[SeriesOut]
    total: int


class SeriesPatch(BaseModel):
    canonical_title: Optional[str] = None
    default_filter: Optional[str] = None
    default_offset: Optional[int] = None
    poster_url: Optional[str] = None


@router.get("/", response_model=SeriesListOut, dependencies=[Depends(get_current_user)])
async def list_series(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
):
    repo = SeriesRepository(session)
    items, total = await repo.list_paginated(limit=limit, offset=offset)
    return SeriesListOut(
        items=[SeriesOut.model_validate(s) for s in items],
        total=total,
    )


@router.get("/{series_id}", response_model=SeriesOut, dependencies=[Depends(get_current_user)])
async def get_series(
    series_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    repo = SeriesRepository(session)
    s = await repo.get_by_id(series_id)
    if s is None:
        raise HTTPException(status_code=404, detail="series not found")
    return SeriesOut.model_validate(s)


@router.patch("/{series_id}", response_model=SeriesOut, dependencies=[Depends(get_current_user)])
async def patch_series(
    series_id: int,
    body: SeriesPatch,
    session: AsyncSession = Depends(get_db_session),
):
    repo = SeriesRepository(session)
    s = await repo.get_by_id(series_id)
    if s is None:
        raise HTTPException(status_code=404, detail="series not found")
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(s, field, value)
    # When canonical_title changes, recompute normalized_title so the
    # fallback identity key (used by non-Mikan resolution in
    # SeriesRepository.get_by_fallback) stays consistent with the new
    # display title. Skip if the caller supplied normalized_title directly
    # (reserved for migrations / admin scripts; not exposed via schema).
    if "canonical_title" in updates:
        from module.domain.text.normalize import normalize_title
        from module.services.identity_resolver import _derive_root_path
        normalized, _cour = normalize_title(updates["canonical_title"])
        s.normalized_title = normalized
        # Root path is derived from canonical_title — never edited
        # independently. Editing the title relocates downloads.
        s.root_path = _derive_root_path(updates["canonical_title"])
    await session.commit()
    await session.refresh(s)
    return SeriesOut.model_validate(s)
