"""/api/v1/health/* — Mikan + concurrency status endpoints (spec §12.1, §12.2)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from module.api.middleware.auth import get_current_user
from module.database.engine import get_db_session
from module.repositories.mikan_ref import MikanEpisodeRefRepository
from module.services.pending_enrichment import PendingEnrichmentService

router = APIRouter(prefix="/health", tags=["health"])

# ---------------------------------------------------------------------------
# Mikan Health
# ---------------------------------------------------------------------------

_OK_HOURS = 1.0
_DEGRADED_HOURS = 24.0
_PENDING_DEGRADED = 3
_FAILURE_DOWN = 10


class MikanPendingItem(BaseModel):
    info_hash: str
    raw_name: str
    homepage: Optional[str] = None
    attempts: int
    last_error: Optional[str] = None
    first_seen_at: Optional[str] = None


class MikanHealthResponse(BaseModel):
    status: str  # ok | degraded | down
    pending_count: int
    last_success_at: Optional[str] = None
    hours_since_last_success: Optional[float] = None
    consecutive_failures: int = 0
    pending_items: list[MikanPendingItem]


def _mikan_status(
    *,
    pending_count: int,
    hours_since: Optional[float],
    failures: int,
) -> str:
    """Compute status per spec §12.2.

    down      : consecutive_failures >= 10  OR  hours_since >= 24
    degraded  : pending_count >= 3  OR  1 <= hours_since < 24
    ok        : otherwise
    """
    if failures >= _FAILURE_DOWN:
        return "down"
    if hours_since is not None and hours_since >= _DEGRADED_HOURS:
        return "down"
    if pending_count >= _PENDING_DEGRADED:
        return "degraded"
    if hours_since is not None and hours_since >= _OK_HOURS:
        return "degraded"
    return "ok"


def _hours_since(dt: Optional[datetime]) -> Optional[float]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
    return round(delta, 3)


@router.get(
    "/mikan",
    response_model=MikanHealthResponse,
    dependencies=[Depends(get_current_user)],
)
async def mikan_health(session: AsyncSession = Depends(get_db_session)):
    pending_svc = PendingEnrichmentService(session)
    mikan_repo = MikanEpisodeRefRepository(session)

    pending = await pending_svc.list_pending()
    last_success_dt: Optional[datetime] = await mikan_repo.last_success_at()
    failures: int = await mikan_repo.consecutive_failures()

    hours_since = _hours_since(last_success_dt)

    last_success_iso: Optional[str] = (
        last_success_dt.isoformat() if last_success_dt is not None else None
    )

    return MikanHealthResponse(
        status=_mikan_status(
            pending_count=len(pending),
            hours_since=hours_since,
            failures=failures,
        ),
        pending_count=len(pending),
        last_success_at=last_success_iso,
        hours_since_last_success=hours_since,
        consecutive_failures=failures,
        pending_items=[
            MikanPendingItem(
                info_hash=item.info_hash,
                raw_name=item.raw_name,
                homepage=item.homepage or None,
                attempts=item.attempt_count,
                last_error=item.last_error,
                first_seen_at=(
                    item.first_seen_at.isoformat() if item.first_seen_at else None
                ),
            )
            for item in pending
        ],
    )


# ---------------------------------------------------------------------------
# Concurrency Health
# ---------------------------------------------------------------------------


class ConcurrencyResponse(BaseModel):
    rss_locks: list[dict]
    rate_limiters: dict


def _snapshot_rss_locks() -> list[dict]:
    """Read per-RSS lock state from the module-level registry singleton.

    Returns empty list when the registry hasn't been initialised yet
    (e.g. before the first RSS refresh fires).
    """
    try:
        from module.scheduler.jobs.rss_refresh import _rss_lock_registry

        if _rss_lock_registry is None:
            return []
        locks_dict: dict = getattr(_rss_lock_registry, "_locks", {})
        return [
            {
                "rss_id": rss_id,
                "held": lock.locked() if hasattr(lock, "locked") else False,
                # TODO(observability): track hold start time to compute held_duration_s
                "held_duration_s": 0.0,
            }
            for rss_id, lock in locks_dict.items()
        ]
    except Exception:
        return []


def _snapshot_rate_limiters() -> dict:
    """Return a snapshot of every registered RateLimiter singleton.

    Keys are service names (e.g. "mikan").  Values expose concurrency
    and degraded state.  queue / in_flight / error_rate_5m are not
    tracked at this stage — stubbed as 0.
    # TODO(observability): add in_flight counter and 5-min error-rate ring buffer
    """
    try:
        from module.concurrency.registry import _LIMITERS

        result: dict = {}
        for name, limiter in _LIMITERS.items():
            result[name] = {
                # Semaphore value is not directly readable via public API; expose
                # concurrency ceiling and degraded flag instead.
                "queue": 0,  # TODO(observability)
                "in_flight": 0,  # TODO(observability)
                "req_per_min": 0,  # TODO(observability)
                "error_rate_5m": 0.0,  # TODO(observability)
                "degraded": limiter.is_degraded(),
                "current_concurrent": limiter.current_concurrent(),
            }
        return result
    except Exception:
        return {}


@router.get(
    "/concurrency",
    response_model=ConcurrencyResponse,
    dependencies=[Depends(get_current_user)],
)
async def concurrency_health() -> ConcurrencyResponse:
    return ConcurrencyResponse(
        rss_locks=_snapshot_rss_locks(),
        rate_limiters=_snapshot_rate_limiters(),
    )
