"""RSS refresh scheduled job.

Periodically refreshes all enabled RSS feeds at configured interval.

Flow per RSS feed:
  1. Fetch raw torrent items from the RSS URL.
  2. Apply global filter (exclusion patterns from settings.rss_parser.filter).
  3. Parse each torrent name via TitleParser to build FeedItem dataclasses.
  4. Delegate to RssPipeline.run_for_feed — which handles:
       - per-RSS concurrency lock (skip-if-held)
       - Mikan enrichment (resolve → create bangumi + torrent)
       - pending queue for unresolvable items
  5. After all feeds, trigger downloader for any un-downloaded torrents.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...conf import settings
from ...concurrency.registry import build_mikan_limiter_from_settings
from ...concurrency.rss_lock import RssLockRegistry
from ...database import get_db_session
from ...domain.models.torrent import Torrent, TorrentState
from ...domain.models.bangumi import Bangumi
from ...domain.parser.title_parser import TitleParser
from ...domain.value_objects import BangumiParsingError, gen_save_path
from ...mikan.client import MikanClient
from ...mikan.resolver import MikanResolver
from ...repositories.mikan_ref import MikanEpisodeRefRepository
from ...repositories.rss import RSSRepository
from ...repositories.torrent import TorrentRepository
from ...services.downloader import create_downloader
from ...services.pipeline.rss_pipeline import FeedItem, RssPipeline
from ...services.rss_engine import RSSEngine

logger = logging.getLogger(__name__)

# Module-level singleton for per-RSS concurrency control.
_rss_lock_registry: Optional[RssLockRegistry] = None


def _get_rss_lock_registry() -> RssLockRegistry:
    global _rss_lock_registry
    if _rss_lock_registry is None:
        _rss_lock_registry = RssLockRegistry()
    return _rss_lock_registry


def _build_global_filter_pattern() -> Optional[str]:
    """Compile global exclusion filter from settings into a single regex pattern.

    Returns None when there is no global filter configured.
    """
    filters = settings.rss_parser.filter
    if not filters:
        return None
    return "|".join(re.escape(f) if not _is_regex(f) else f for f in filters)


def _is_regex(pattern: str) -> bool:
    """Heuristic: treat pattern as raw regex when it contains regex metacharacters."""
    return bool(re.search(r"[\\^$.*+?{}|\[\]()]", pattern))


def _is_globally_filtered(torrent_name: str, global_pattern: Optional[str]) -> bool:
    """Return True when `torrent_name` matches the global exclusion pattern."""
    if not global_pattern:
        return False
    return bool(re.search(global_pattern, torrent_name, re.IGNORECASE))


def _build_feed_item(
    torrent: Torrent,
    rss_id: int,
    rss_url: str,
    parsed_title: str,
    parsed_season: int,
    parsed_poster: Optional[str],
) -> FeedItem:
    """Convert a raw Torrent + parse result into a FeedItem for the pipeline."""
    return FeedItem(
        info_hash=torrent.hash or "",
        raw_name=torrent.name,
        homepage=torrent.homepage,
        url=torrent.url,
        rss_id=rss_id,
        published_at=None,  # parse_rss_feed does not expose publish time
        rss_link=rss_url,
        parsed_title=parsed_title,
        parsed_season=parsed_season,
        parsed_poster=parsed_poster,
    )


def _parse_torrent_title(
    torrent_name: str,
) -> tuple[str, int, Optional[str]]:
    """Parse torrent name and extract title, season, poster fields.

    Returns (parsed_title, parsed_season, parsed_poster).
    Falls back to the raw name as title and season=1 on parse failure.
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


async def _trigger_downloads(
    session: AsyncSession,
    downloader,
) -> None:
    """Trigger downloader for all torrent rows that are not yet downloaded.

    Uses a 3-phase READ → NETWORK → WRITE approach to minimise lock contention.
    """
    stmt = (
        select(Torrent)
        .where(
            and_(
                Torrent.downloaded == False,  # noqa: E712
                Torrent.state != TorrentState.EXCLUDED,
                Torrent.bangumi_id.is_not(None),
                Torrent.url.is_not(None),
                Torrent.url != "",
            )
        )
    )
    result = await session.execute(stmt)
    pending_torrents = list(result.scalars().all())

    if not pending_torrents:
        return

    # Gather unique bangumi IDs and load bangumi rows in one round-trip.
    bangumi_ids = {t.bangumi_id for t in pending_torrents if t.bangumi_id}
    if not bangumi_ids:
        return

    from sqlalchemy.orm import selectinload
    bangumi_stmt = (
        select(Bangumi)
        .options(selectinload(Bangumi.series))
        .where(Bangumi.id.in_(bangumi_ids))
    )
    bangumi_result = await session.execute(bangumi_stmt)
    bangumi_map: dict[int, Bangumi] = {
        b.id: b for b in bangumi_result.scalars().all()
    }

    # Phase 2: NETWORK — submit each torrent to the downloader.
    from pathlib import PurePosixPath
    torrent_repo = TorrentRepository(session)
    for torrent in pending_torrents:
        bangumi = bangumi_map.get(torrent.bangumi_id)
        if bangumi is None:
            continue

        _rr_series = bangumi.series
        _rr_title = _rr_series.canonical_title if _rr_series is not None else ""
        _rr_season = _rr_series.season if _rr_series is not None else 1
        _rr_root = _rr_series.root_path if _rr_series is not None else None
        _rr_full = (
            bangumi.path_override
            or (str(PurePosixPath(_rr_root) / f"Season {_rr_season}") if _rr_root else None)
        )
        save_path = _rr_full or gen_save_path(
            settings.downloader.path,
            _rr_title,
            _rr_season,
        )

        try:
            success = await downloader.add_torrents(
                urls=[torrent.url],
                save_path=save_path,
                torrent_files=None,
            )
            if success and torrent.hash:
                await torrent_repo.mark_downloaded_by_hash(
                    torrent.hash, bangumi.id, save_path
                )
                logger.debug(
                    "[rss_refresh] triggered download: name=%s save_path=%s",
                    torrent.name, save_path,
                )
        except Exception as exc:
            logger.error(
                "[rss_refresh] download failed for torrent %s: %s",
                torrent.name, exc,
            )


async def rss_refresh_job() -> None:
    """Refresh all enabled RSS feeds.

    Registered with scheduler at settings.program.rss_time interval (default 900s).
    Delegates feed processing to RssPipeline for lock + mikan enrichment + create.
    Errors are logged but do not crash the scheduler.
    """
    try:
        async_session_gen = get_db_session()
        session: AsyncSession = await async_session_gen.__anext__()

        try:
            downloader = create_downloader(settings, session=session)
            limiter = build_mikan_limiter_from_settings()
            lock_registry = _get_rss_lock_registry()

            async with MikanClient(
                base_url=settings.mikan.base_url,
                timeout_seconds=settings.mikan.timeout_seconds,
            ) as mikan_client:
                mikan_ref_repo = MikanEpisodeRefRepository(session)
                resolver = MikanResolver(
                    client=mikan_client,
                    limiter=limiter,
                    mikan_ref_repo=mikan_ref_repo,
                )

                pipeline = RssPipeline(
                    session,
                    lock_registry=lock_registry,
                    mikan_resolver=resolver,
                )

                rss_repo = RSSRepository(session)
                rss_items = await rss_repo.get_enabled()

                global_filter_pattern = _build_global_filter_pattern()

                for rss in rss_items:
                    if rss.last_status == "Recreating":
                        logger.debug(
                            "[rss_refresh] skip rss_id=%d name=%s — recreation in progress",
                            rss.id, rss.name,
                        )
                        continue

                    try:
                        raw_torrents = await RSSEngine.parse_rss_feed(rss.url)
                    except Exception as exc:
                        logger.error(
                            "[rss_refresh] fetch failed rss_id=%d name=%s: %s",
                            rss.id, rss.name, exc,
                        )
                        await rss_repo.update_status(rss.id, "Error", str(exc))
                        await session.commit()
                        continue

                    feed_items: list[FeedItem] = []
                    for torrent in raw_torrents:
                        # Skip items matching global exclusion filter.
                        if _is_globally_filtered(torrent.name, global_filter_pattern):
                            logger.debug(
                                "[rss_refresh] global-filtered: %s", torrent.name
                            )
                            continue

                        if not torrent.hash:
                            logger.debug(
                                "[rss_refresh] skip torrent with no hash: %s",
                                torrent.name,
                            )
                            continue

                        parsed_title, parsed_season, parsed_poster = (
                            await asyncio.to_thread(_parse_torrent_title, torrent.name)
                        )
                        feed_items.append(
                            _build_feed_item(
                                torrent=torrent,
                                rss_id=rss.id,
                                rss_url=rss.url,
                                parsed_title=parsed_title,
                                parsed_season=parsed_season,
                                parsed_poster=parsed_poster,
                            )
                        )

                    pipeline_result = await pipeline.run_for_feed(rss.id, feed_items)
                    logger.info(
                        "[rss_refresh] rss_id=%d name=%s pipeline=%s",
                        rss.id, rss.name, pipeline_result,
                    )

                    await rss_repo.update_status(rss.id, "Success", None)
                    await session.commit()

                # After all feeds processed, trigger downloader for pending torrents.
                await _trigger_downloads(session, downloader)
                await session.commit()

            logger.info("[rss_refresh] job completed successfully")

        finally:
            await session.close()

    except Exception as exc:
        logger.exception("[rss_refresh] job error: %s", exc)
