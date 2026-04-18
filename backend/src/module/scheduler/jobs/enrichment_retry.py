"""Scheduled job: drain pending_torrent_enrichment via MikanResolver.

For each pending row:
  - resolver.resolve(info_hash) → MikanRef | None | raises
  - on success: bump attempt_count + mark "(resolved; awaiting pipeline integration)"
    (full bangumi+torrent creation is wired in by a later task)
  - on None/raise: bump attempt_count + record error string

The row is NOT removed here — it's intentionally kept queued so the
pipeline integration step has work to do.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from module.services.pending_enrichment import PendingEnrichmentService

logger = logging.getLogger(__name__)


async def drain_pending(
    session: AsyncSession,
    *,
    mikan_resolver: Any,
) -> dict[str, int]:
    """Drain the pending_torrent_enrichment queue.

    Args:
        session: Async SQLAlchemy session.
        mikan_resolver: Any object with ``resolve(info_hash: str)`` coroutine.

    Returns:
        Summary dict with keys: attempted, resolved, still_pending.
    """
    svc = PendingEnrichmentService(session)
    pending = await svc.list_pending()
    summary: dict[str, int] = {"attempted": 0, "resolved": 0, "still_pending": 0}

    for item in pending:
        summary["attempted"] += 1
        try:
            ref = await mikan_resolver.resolve(item.info_hash)
        except Exception as exc:
            error_msg = f"{type(exc).__name__}: {exc}"
            logger.warning("[enrichment_retry] %s failed: %s", item.info_hash, error_msg)
            await svc.mark_attempted(item.info_hash, error=error_msg)
            summary["still_pending"] += 1
            continue

        if ref is None:
            await svc.mark_attempted(item.info_hash, error="resolver returned None")
            summary["still_pending"] += 1
            continue

        # Resolved — full pipeline integration (creating torrent + bangumi)
        # is iterative; keep the row queued with a marker for now.
        await svc.mark_attempted(
            item.info_hash,
            error="(resolved; awaiting pipeline integration)",
        )
        summary["resolved"] += 1
        logger.debug("[enrichment_retry] %s resolved: %s", item.info_hash, ref)

    await session.commit()
    logger.info("[enrichment_retry] %s", summary)
    return summary


async def enrichment_retry_job() -> None:
    """Scheduled job wrapper for drain_pending.

    Registered with scheduler at settings.program.enrichment_retry_time interval (default 300s).
    Errors are logged but don't crash the scheduler.
    """
    try:
        from module.concurrency.registry import build_mikan_limiter_from_settings
        from module.conf import settings
        from module.database import get_db_session
        from module.mikan.client import MikanClient
        from module.mikan.resolver import MikanResolver
        from module.repositories.mikan_ref import MikanEpisodeRefRepository
        from sqlalchemy.ext.asyncio import AsyncSession

        async_session_gen = get_db_session()
        session: AsyncSession = await async_session_gen.__anext__()

        try:
            limiter = build_mikan_limiter_from_settings()
            async with MikanClient(
                base_url=settings.mikan.base_url,
                timeout_seconds=settings.mikan.timeout_seconds,
            ) as client:
                mikan_ref_repo = MikanEpisodeRefRepository(session)
                resolver = MikanResolver(
                    client=client,
                    limiter=limiter,
                    mikan_ref_repo=mikan_ref_repo,
                )
                summary = await drain_pending(session, mikan_resolver=resolver)
            logger.info("[enrichment_retry] job completed: %s", summary)
        finally:
            await session.close()

    except Exception as exc:
        logger.exception("[enrichment_retry] job error: %s", exc)
