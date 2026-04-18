"""Scheduled job: drain pending_torrent_enrichment via MikanResolver.

For each pending row:
  - resolver.resolve(info_hash) → MikanRef | None | raises
  - on MikanRef: hand off to ``finalize_resolved_item`` which creates the
    Series / Bangumi / Torrent rows and removes the pending entry
  - on None: mark attempt, keep row queued with last_error
  - on raise: mark attempt, keep row queued with the exception class+message
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from module.domain.parser.title_parser import TitleParser
from module.domain.value_objects import BangumiParsingError
from module.repositories.rss import RSSRepository
from module.services.pending_enrichment import PendingEnrichmentService
from module.services.pipeline.rss_pipeline import FeedItem, finalize_resolved_item

logger = logging.getLogger(__name__)


def _parse_torrent_title(
    torrent_name: str,
) -> tuple[str, int, Optional[str]]:
    """Best-effort reparse — mirrors rss_refresh._parse_torrent_title.

    Returns (parsed_title, parsed_season, parsed_poster) with safe fallbacks
    on any parser error so a malformed pending row can still be retried.
    """
    try:
        parser = TitleParser()
        bangumi_data = parser.raw_parser(torrent_name)
        if bangumi_data:
            return (
                bangumi_data.official_title or torrent_name,
                bangumi_data.season or 1,
                getattr(bangumi_data, "poster_link", None),
            )
    except BangumiParsingError:
        pass
    except Exception:
        pass
    return torrent_name, 1, None


async def _build_feed_item_from_pending(
    row,
    *,
    rss_repo: RSSRepository,
) -> Optional[FeedItem]:
    """Reconstruct a FeedItem for finalize_resolved_item from a pending row.

    Returns None when the owning RSS has been deleted — the pending row stays
    queued and the caller should skip finalization.
    """
    rss = await rss_repo.get_by_id(row.rss_id)
    if rss is None:
        return None

    parsed_title, parsed_season, parsed_poster = await asyncio.to_thread(
        _parse_torrent_title, row.raw_name
    )
    return FeedItem(
        info_hash=row.info_hash,
        raw_name=row.raw_name,
        homepage=row.homepage or None,
        url=row.url,
        rss_id=row.rss_id,
        published_at=row.published_at,
        rss_link=rss.url,
        parsed_title=parsed_title,
        parsed_season=parsed_season,
        parsed_poster=parsed_poster,
    )


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
    rss_repo = RSSRepository(session)
    pending = await svc.list_pending()
    summary: dict[str, int] = {"attempted": 0, "resolved": 0, "still_pending": 0}

    for row in pending:
        summary["attempted"] += 1
        try:
            ref = await mikan_resolver.resolve(row.info_hash)
        except Exception as exc:
            error_msg = f"{type(exc).__name__}: {exc}"
            logger.warning("[enrichment_retry] %s failed: %s", row.info_hash, error_msg)
            await svc.mark_attempted(row.info_hash, error=error_msg)
            summary["still_pending"] += 1
            continue

        if ref is None:
            await svc.mark_attempted(row.info_hash, error="resolver returned None")
            summary["still_pending"] += 1
            continue

        feed_item = await _build_feed_item_from_pending(row, rss_repo=rss_repo)
        if feed_item is None:
            await svc.mark_attempted(
                row.info_hash, error=f"rss_id={row.rss_id} no longer exists"
            )
            summary["still_pending"] += 1
            continue

        try:
            await finalize_resolved_item(session, item=feed_item, mikan_ref=ref)
        except Exception as exc:
            error_msg = f"finalize_failed: {type(exc).__name__}: {exc}"
            logger.exception(
                "[enrichment_retry] finalize failed for %s: %s", row.info_hash, exc
            )
            await svc.mark_attempted(row.info_hash, error=error_msg)
            summary["still_pending"] += 1
            continue

        summary["resolved"] += 1
        logger.debug("[enrichment_retry] %s resolved and persisted", row.info_hash)

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
