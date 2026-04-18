"""End-to-end RSS feed processor: lock → resolve → create | enqueue.

This is the single chokepoint for the RSS refresh path. It owns:
  - per-RSS concurrency (skip-if-held, spec §9.1)
  - Mikan enrichment via the rate-limited resolver (spec §8.3)
  - branching: resolved → create torrent + bangumi; unresolved → enqueue
    in pending_torrent_enrichment

Callers (rss_refresh job, manual refresh API) pass already-fetched feed
items as a list of FeedItem dataclasses, so the pipeline stays framework-
free and is easy to test with fakes.

Note: MikanResolver.resolve() takes info_hash (not homepage_url) — it
fetches the episode page keyed by hash and returns a MikanRef or None.
The homepage field on FeedItem is used only to decide whether to attempt
resolution (Branch A: no homepage → skip resolver entirely).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from module.concurrency.rss_lock import RssLockRegistry
from module.mikan.parser import MikanRef
from module.mikan.resolver import MikanResolver
from module.repositories.bangumi import BangumiRepository
from module.repositories.torrent import TorrentRepository
from module.services.identity_resolver import resolve_series_for_rss
from module.services.pending_enrichment import PendingEnrichmentService

logger = logging.getLogger(__name__)


@dataclass
class FeedItem:
    """Raw RSS item shape consumed by the pipeline."""

    info_hash: str
    raw_name: str
    homepage: Optional[str]
    url: str
    rss_id: int
    published_at: Optional[datetime]
    rss_link: str           # RSS subscribe URL (Mikan format gives bangumiId+subgroupid)
    parsed_title: str       # title parsed from torrent name
    parsed_season: int
    parsed_poster: Optional[str]


@dataclass
class PipelineResult:
    skipped_locked: bool = False
    items_seen: int = 0
    items_enqueued: int = 0
    items_resolved: int = 0
    items_failed: int = 0


class _Pending(Exception):
    """Internal control-flow signal: this item went to the pending queue."""


class RssPipeline:
    def __init__(
        self,
        session: AsyncSession,
        *,
        lock_registry: RssLockRegistry,
        mikan_resolver: MikanResolver,
    ) -> None:
        self.session = session
        self.lock_registry = lock_registry
        self.mikan_resolver = mikan_resolver
        self._pending = PendingEnrichmentService(session)
        self._bangumi_repo = BangumiRepository(session)
        self._torrent_repo = TorrentRepository(session)

    async def run_for_feed(
        self, rss_id: int, items: list[FeedItem]
    ) -> PipelineResult:
        """Process every item in `items` under a per-RSS lock.

        If another task holds rss_id's lock, returns immediately with
        skipped_locked=True (spec §9.1).
        """
        result = PipelineResult()

        lock = await self.lock_registry.try_acquire(rss_id)
        if lock is None:
            logger.info("[pipeline] skip rss_id=%d (lock held)", rss_id)
            result.skipped_locked = True
            return result

        try:
            for item in items:
                result.items_seen += 1
                try:
                    await self._process_item(item)
                    result.items_resolved += 1
                except _Pending:
                    result.items_enqueued += 1
                except Exception as exc:
                    logger.exception("[pipeline] item failed: hash=%s error=%s", item.info_hash, exc)
                    result.items_failed += 1
            await self.session.commit()
        finally:
            lock.release()

        return result

    async def _process_item(self, item: FeedItem) -> None:
        # Branch A: no homepage at all → directly pending (no network needed).
        if not item.homepage:
            await self._pending.enqueue(
                info_hash=item.info_hash,
                raw_name=item.raw_name,
                homepage=None,
                url=item.url,
                rss_id=item.rss_id,
                published_at=item.published_at,
            )
            raise _Pending

        # Branch B: try to resolve via Mikan using info_hash as the page key.
        mikan_ref = await self.mikan_resolver.resolve(item.info_hash)
        if mikan_ref is None:
            await self._pending.enqueue(
                info_hash=item.info_hash,
                raw_name=item.raw_name,
                homepage=item.homepage,
                url=item.url,
                rss_id=item.rss_id,
                published_at=item.published_at,
            )
            raise _Pending

        # Branch C: resolved → ensure Series + Bangumi + Torrent exist.
        await finalize_resolved_item(
            self.session, item=item, mikan_ref=mikan_ref
        )


async def finalize_resolved_item(
    session: AsyncSession,
    *,
    item: FeedItem,
    mikan_ref: MikanRef,
) -> None:
    """Persist the Series → Bangumi → Torrent chain for a resolved feed item.

    Shared by ``RssPipeline._process_item`` (live RSS refresh) and the
    enrichment_retry drain job. The caller-supplied ``mikan_ref`` (from the
    Mikan episode page) wins over whatever could be parsed from ``rss_link``
    query parameters (review H-2). Removes any matching pending_enrichment row
    on success.
    """
    resolved = await resolve_series_for_rss(
        session=session,
        rss_link=item.rss_link,
        parsed_title=item.parsed_title,
        parsed_season=item.parsed_season,
        parsed_poster=item.parsed_poster,
        mikan_ref=mikan_ref,
    )

    bangumi_repo = BangumiRepository(session)
    torrent_repo = TorrentRepository(session)

    bangumi = await bangumi_repo.get_by_series_and_subgroup(
        resolved.series.id, mikan_ref.mikan_subgroup_id
    )
    if bangumi is None:
        bangumi = await bangumi_repo.create({
            "series_id": resolved.series.id,
            "mikan_subgroup_id": mikan_ref.mikan_subgroup_id,
            "rss_id": item.rss_id,
            "rss_link": item.rss_link,
            "group_name": "Unknown",
            "active": True,
        })

    await torrent_repo.create({
        "bangumi_id": bangumi.id,
        "rss_id": item.rss_id,
        "name": item.raw_name,
        "url": item.url,
        "hash": item.info_hash,
        "homepage": item.homepage,
        "mikan_bangumi_id": mikan_ref.mikan_bangumi_id,
        "mikan_subgroup_id": mikan_ref.mikan_subgroup_id,
    })

    # Successful resolution clears any prior pending row for this hash.
    await PendingEnrichmentService(session).remove(item.info_hash)
