"""/api/v1/pending-resolution/* — inspect + manually retry the pending queue."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from module.api.middleware.auth import get_current_user
from module.conf import settings
from module.database.engine import get_db_session
from module.domain.models.pending_enrichment import PendingTorrentEnrichment
from module.mikan.parser import (
    build_canonical_bangumi_url,
    parse_canonical_bangumi_url,
)
from module.repositories.bangumi import BangumiRepository
from module.services.identity_resolver import resolve_series_for_rss
from module.services.pending_enrichment import PendingEnrichmentService

router = APIRouter(prefix="/pending-resolution", tags=["pending-resolution"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class PendingItem(BaseModel):
    info_hash: str
    raw_name: str
    homepage: Optional[str] = None
    url: str
    rss_id: int
    first_seen_at: Optional[str] = None
    attempt_count: int
    last_error: Optional[str] = None
    last_attempt_at: Optional[str] = None


class PendingList(BaseModel):
    items: list[PendingItem]
    total: int


class RetryResponse(BaseModel):
    info_hash: str
    resolved: bool
    mikan_bangumi_id: Optional[int] = None
    mikan_subgroup_id: Optional[int] = None
    error: Optional[str] = None


class ResolveRequest(BaseModel):
    mikan_bangumi_url: str
    title: str
    season: int = 1


class ResolveResponse(BaseModel):
    info_hash: str
    bangumi_id: int
    mikan_bangumi_url: str
    short_circuited: bool


# ---------------------------------------------------------------------------
# Resolver bootstrap (testable seam via monkeypatch)
# ---------------------------------------------------------------------------


def _build_resolver_for_retry(session: AsyncSession) -> Any:
    """Return an async context manager that yields a resolver with .resolve(info_hash).

    Tests monkeypatch this name to inject a fake.  Production wires the real
    MikanResolver + MikanClient the same way enrichment_retry_job does.
    """
    return _ResolverContext(session)


class _ResolverContext:
    """Async context manager: MikanClient + MikanResolver per request."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._client: Any = None
        self._resolver: Any = None

    async def __aenter__(self) -> Any:
        from module.concurrency.registry import build_mikan_limiter_from_settings
        from module.conf import settings
        from module.mikan.client import MikanClient
        from module.mikan.resolver import MikanResolver
        from module.repositories.mikan_ref import MikanEpisodeRefRepository

        limiter = build_mikan_limiter_from_settings()
        self._client = MikanClient(
            base_url=settings.mikan.base_url,
            timeout_seconds=settings.mikan.timeout_seconds,
        )
        await self._client.__aenter__()
        mikan_ref_repo = MikanEpisodeRefRepository(self._session)
        self._resolver = MikanResolver(
            client=self._client,
            limiter=limiter,
            mikan_ref_repo=mikan_ref_repo,
        )
        return self._resolver

    async def __aexit__(self, *args: Any) -> None:
        if self._client is not None:
            await self._client.__aexit__(*args)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/", response_model=PendingList, dependencies=[Depends(get_current_user)])
async def list_pending(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
) -> PendingList:
    svc = PendingEnrichmentService(session)
    all_items = await svc.list_pending()
    total = len(all_items)
    window = all_items[offset : offset + limit]
    return PendingList(
        items=[
            PendingItem(
                info_hash=i.info_hash,
                raw_name=i.raw_name,
                homepage=i.homepage or None,
                url=i.url,
                rss_id=i.rss_id,
                first_seen_at=i.first_seen_at.isoformat() if i.first_seen_at else None,
                attempt_count=i.attempt_count,
                last_error=i.last_error,
                last_attempt_at=(
                    i.last_attempt_at.isoformat() if i.last_attempt_at else None
                ),
            )
            for i in window
        ],
        total=total,
    )


@router.post(
    "/{info_hash}/retry",
    response_model=RetryResponse,
    dependencies=[Depends(get_current_user)],
)
async def retry_pending(
    info_hash: str,
    session: AsyncSession = Depends(get_db_session),
) -> RetryResponse:
    row = (
        await session.execute(
            select(PendingTorrentEnrichment).where(
                PendingTorrentEnrichment.info_hash == info_hash
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, f"pending info_hash {info_hash!r} not found")

    svc = PendingEnrichmentService(session)
    resolver_ctx = _build_resolver_for_retry(session)
    try:
        async with resolver_ctx as resolver:
            try:
                ref = await resolver.resolve(info_hash)
            except Exception as exc:
                error_msg = f"{type(exc).__name__}: {exc}"
                await svc.mark_attempted(info_hash, error=error_msg)
                await session.commit()
                return RetryResponse(info_hash=info_hash, resolved=False, error=error_msg)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc

    if ref is None:
        await svc.mark_attempted(info_hash, error="resolver returned None")
        await session.commit()
        return RetryResponse(
            info_hash=info_hash, resolved=False, error="resolver returned None"
        )

    # Row stays in queue; pipeline integration is a later task.
    await svc.mark_attempted(
        info_hash, error="(resolved; awaiting pipeline integration)"
    )
    await session.commit()
    return RetryResponse(
        info_hash=info_hash,
        resolved=True,
        mikan_bangumi_id=ref.mikan_bangumi_id,
        mikan_subgroup_id=ref.mikan_subgroup_id,
    )


@router.post(
    "/{info_hash}/resolve",
    response_model=ResolveResponse,
    dependencies=[Depends(get_current_user)],
)
async def resolve_pending(
    info_hash: str,
    body: ResolveRequest,
    session: AsyncSession = Depends(get_db_session),
) -> ResolveResponse:
    """Operator-supplied bangumi identity for a torrent the parser gave up on.

    Spec §8.3 human-in-the-loop flow:
    - Operator pastes the canonical Mikan bangumi-page URL
      (``https://mikanani.me/Home/Bangumi/<bid>#<sid>``) and a title override.
    - We create a Bangumi row stamped with ``mikan_bangumi_url`` so future
      RSS items with the same Mikan page short-circuit the parser path.
    - The pending row is removed on success; the torrent itself is *not*
      built here — RSSEngine will re-ingest it on the next refresh and bind
      automatically via the short-circuit.
    """
    ids = parse_canonical_bangumi_url(body.mikan_bangumi_url)
    if ids is None:
        raise HTTPException(
            400,
            "mikan_bangumi_url must contain /Home/Bangumi/<id>#<sub>",
        )
    bangumi_id_m, subgroup_id = ids
    canonical = build_canonical_bangumi_url(bangumi_id_m, subgroup_id)

    title = body.title.strip()
    if not title:
        raise HTTPException(400, "title is required")

    row = (
        await session.execute(
            select(PendingTorrentEnrichment).where(
                PendingTorrentEnrichment.info_hash == info_hash
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, f"pending info_hash {info_hash!r} not found")

    pending_rss_id = row.rss_id
    bangumi_repo = BangumiRepository(session)
    svc = PendingEnrichmentService(session)

    existing = await bangumi_repo.get_by_mikan_bangumi_url(canonical)
    if existing is not None:
        await svc.remove(info_hash)
        await session.commit()
        return ResolveResponse(
            info_hash=info_hash,
            bangumi_id=existing.id,
            mikan_bangumi_url=canonical,
            short_circuited=True,
        )

    resolved = await resolve_series_for_rss(
        session,
        rss_link=canonical,
        parsed_title=title,
        parsed_season=body.season,
    )

    default_filter = ",".join(settings.rss_parser.filter)
    created = await bangumi_repo.create({
        "series_id": resolved.series.id,
        "mikan_subgroup_id": subgroup_id,
        "mikan_bangumi_url": canonical,
        "group_name": "Unknown",
        "rss_link": "",
        "rss_id": pending_rss_id,
        "filter": default_filter,
        "eps_collect": False,
        "offset": 0,
        "added": True,
        "deleted": False,
        "pending_review": False,
        "active": True,
    })

    await svc.remove(info_hash)
    await session.commit()

    return ResolveResponse(
        info_hash=info_hash,
        bangumi_id=created.id,
        mikan_bangumi_url=canonical,
        short_circuited=False,
    )
