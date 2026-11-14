"""/api/v1/series/* endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from module.api.middleware.auth import get_current_user
from module.conf import settings
from module.concurrency.rename_lock import rename_lock_guard
from module.database.engine import get_db_session
from module.domain.text.normalize import normalize_title
from module.repositories.bangumi import BangumiRepository
from module.repositories.series import SeriesRepository
from module.services.downloader.factory import create_downloader
from module.services.identity_resolver import _derive_root_path
from module.services.renamer import RenamerService

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
    if updates.get("default_filter") == "":
        updates["default_filter"] = None

    if updates.get("canonical_title", s.canonical_title) == s.canonical_title:
        _apply_patch(s, updates)
        await session.commit()
        await session.refresh(s)
        return SeriesOut.model_validate(s)

    # The title names both the root folder and every episode file, so a
    # title change re-renames the series' files into the new root now.
    async with rename_lock_guard() as lock:
        if lock is None:
            return JSONResponse(
                status_code=409,
                content={
                    "msg_en": "Rename is already in progress. Please try Save again shortly.",
                    "msg_zh": "当前正在执行重命名，请稍后再试。",
                },
            )
        _apply_patch(s, updates)
        await session.commit()
        await session.refresh(s)
        downloader = create_downloader(settings, session)
        renamer = RenamerService(session, rename_method=settings.bangumi_manage.rename_method)
        for bangumi in await BangumiRepository(session).list_by_series(s.id):
            if bangumi.path_override:
                continue
            await renamer.rename_bangumi(downloader, bangumi.id, retrigger=True)
    return SeriesOut.model_validate(s)


def _apply_patch(s, updates: dict) -> None:
    for field, value in updates.items():
        setattr(s, field, value)
    if "canonical_title" in updates:
        # normalized_title is the fallback identity key and root_path is
        # derived from the title; neither is edited independently.
        s.normalized_title, _cour = normalize_title(updates["canonical_title"])
        s.root_path = _derive_root_path(updates["canonical_title"])
