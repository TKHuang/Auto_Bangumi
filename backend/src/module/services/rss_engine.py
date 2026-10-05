"""RSS Engine Service - Async RSS feed processing with atomic transactions."""

import asyncio
import logging
import re

from sqlalchemy.ext.asyncio import AsyncSession

from module.conf import settings
from module.domain.models.bangumi import Bangumi
from module.domain.models.torrent import Torrent
from module.domain.value_objects import gen_save_path
from module.mikan.parser import (
    extract_mikan_ids_from_rss,
)
from module.network.request_contents import RequestContent
from module.repositories.bangumi import BangumiRepository
from module.repositories.torrent import TorrentRepository
from module.services.downloader.interface import DownloaderProtocol

logger = logging.getLogger(__name__)


class RSSEngine:
    """RSS Engine for feed processing and torrent management."""

    @staticmethod
    async def _record_pending_candidate(
        session: AsyncSession,
        *,
        torrent: Torrent,
        bangumi: Bangumi,
        rss_item,
        mikan_bangumi_id: int | None = None,
        mikan_subgroup_id: int | None = None,
        rss_id: int | None = None,
    ) -> bool:
        candidate_rss_id = rss_id if rss_id is not None else rss_item.id
        return await TorrentRepository(session).create_or_ignore({
            "bangumi_id": bangumi.id,
            "rss_id": candidate_rss_id,
            "name": torrent.name,
            "url": torrent.url,
            "homepage": torrent.homepage,
            "hash": torrent.hash,
            "mikan_bangumi_id": mikan_bangumi_id,
            "mikan_subgroup_id": mikan_subgroup_id,
        })

    @staticmethod
    async def collect_pending_candidates_from_source(
        session: AsyncSession,
        bangumi_id: int,
    ) -> int:
        """Store source-RSS torrents for a pending review bangumi.

        This mirrors eps_complete_from_source for manual review: a bangumi
        discovered from aggregate RSS can preview the whole source feed before
        activation, while keeping every torrent undownloaded until the user
        confirms the selection.
        """
        bangumi_repo = BangumiRepository(session)
        bangumi = await bangumi_repo.get_by_id(bangumi_id)
        if not bangumi or not bangumi.pending_review or not bangumi.rss_link:
            return 0

        def _fetch():
            with RequestContent() as req:
                legacy_torrents = req.get_torrents(bangumi.rss_link, _filter="")
                return [
                    Torrent(
                        name=t.name,
                        url=t.url,
                        homepage=t.homepage,
                        hash=t.hash,
                    )
                    for t in legacy_torrents
                ]

        try:
            all_torrents = await asyncio.to_thread(_fetch)
        except Exception as exc:
            logger.warning(
                "[Engine] Failed to collect pending candidates from source for bangumi=%s: %s",
                bangumi_id,
                exc,
            )
            return 0

        mikan_bangumi_id, mikan_subgroup_id = extract_mikan_ids_from_rss(
            bangumi.rss_link
        )
        if mikan_bangumi_id is not None and mikan_subgroup_id is not None:
            candidates = all_torrents
        else:
            _canonical = (
                bangumi.series.canonical_title
                if bangumi.series is not None
                else ""
            )
            title_matched = [
                torrent
                for torrent in all_torrents
                if _canonical and _canonical in torrent.name
            ]
            candidates = title_matched or all_torrents

        inserted = 0
        for torrent in candidates:
            if await RSSEngine._record_pending_candidate(
                session,
                torrent=torrent,
                bangumi=bangumi,
                rss_item=bangumi,
                rss_id=bangumi.rss_id,
                mikan_bangumi_id=mikan_bangumi_id,
                mikan_subgroup_id=mikan_subgroup_id,
            ):
                inserted += 1
        return inserted

    @staticmethod
    async def parse_rss_feed(url: str) -> list[Torrent]:
        """Parse RSS feed and extract torrents.

        Args:
            url: RSS feed URL

        Returns:
            List of Torrent objects
        """

        def _fetch():
            with RequestContent() as req:
                legacy_torrents = req.get_torrents(url, _filter="")
                return [
                    Torrent(
                        name=t.name,
                        url=t.url,
                        homepage=t.homepage,
                        hash=t.hash,
                    )
                    for t in legacy_torrents
                ]

        torrents = await asyncio.to_thread(_fetch)
        return torrents

    @staticmethod
    def torrent_excluded_by_filter(torrent_name: str, bangumi_filter: str) -> bool:
        """Shared exclusion rule for matching, pending preview and download."""
        if not bangumi_filter:
            return False
        pattern = bangumi_filter.replace(",", "|")
        return bool(re.search(pattern, torrent_name, re.IGNORECASE))

    @staticmethod
    async def download_bangumi(
        session: AsyncSession,
        downloader: DownloaderProtocol,
        bangumi_id: int,
        included_hashes: list[str] | None = None,
    ) -> dict:
        """Download all episodes for bangumi (collection/backfill).

        Uses 3-phase approach: READ → NETWORK → SHORT WRITE to avoid holding
        DB write locks during slow downloader API calls.
        """
        bangumi_repo = BangumiRepository(session)
        torrent_repo = TorrentRepository(session)

        # --- Phase 1: READ (gather data, no writes) ---
        bangumi = await bangumi_repo.get_by_id(bangumi_id)
        if not bangumi:
            return {
                "status": False,
                "message": "Bangumi not found",
                "count": 0,
            }

        def _fetch():
            with RequestContent() as req:
                legacy_torrents = req.get_torrents(bangumi.rss_link, _filter="")
                return [
                    Torrent(
                        name=t.name,
                        url=t.url,
                        homepage=t.homepage,
                        hash=t.hash,
                    )
                    for t in legacy_torrents
                ]

        all_torrents = await asyncio.to_thread(_fetch)

        if not all_torrents:
            return {
                "status": False,
                "message": "No torrents found in RSS feed",
                "count": 0,
            }

        # Title match: only keep torrents whose name contains this bangumi's
        # canonical title, to avoid cross-contamination when a Mikan per-bangumi
        # feed returns torrents from other subgroups / shows.
        _canonical = bangumi.series.canonical_title if bangumi.series is not None else ""
        title_matched = []
        for torrent in all_torrents:
            if _canonical and _canonical in torrent.name:
                title_matched.append(torrent)

        # A per-bangumi Mikan RSS link is already scoped by bangumiId/subgroupid.
        # Fansub release titles often use aliases that do not contain Mikan's
        # canonical Chinese title, so title substring matching must not be the
        # deciding identity check for those feeds.
        if not title_matched:
            title_matched = all_torrents

        if not title_matched:
            logger.debug(
                f"[Engine] download_bangumi {bangumi_id}: no torrent in "
                f"{bangumi.rss_link} matched canonical {_canonical!r}; skipping backfill"
            )
            return {
                "status": True,
                "message": "No torrents matched bangumi title",
                "count": 0,
            }

        included_hash_set = {
            h.lower() for h in (included_hashes or []) if h
        }

        filtered_torrents = [
            torrent
            for torrent in title_matched
            if (torrent.hash and torrent.hash.lower() in included_hash_set)
            or not RSSEngine.torrent_excluded_by_filter(torrent.name, bangumi.filter)
        ]

        if not filtered_torrents:
            return {
                "status": False,
                "message": "All torrents filtered out",
                "count": 0,
            }

        existing_torrents = await torrent_repo.get_by_bangumi(bangumi.id)
        existing_by_hash = {
            existing.hash: existing
            for existing in existing_torrents
            if existing.hash
        }

        new_torrents = []
        for torrent in filtered_torrents:
            torrent.bangumi_id = bangumi.id
            torrent.rss_id = bangumi.rss_id

            if torrent.hash:
                existing = existing_by_hash.get(torrent.hash)
                if existing and (
                    existing.downloaded or torrent_repo.is_excluded(existing)
                ):
                    continue
                new_torrents.append(torrent)
            else:
                new_torrents.append(torrent)

        if not new_torrents:
            return {
                "status": True,
                "message": "No new torrents to download",
                "count": 0,
            }

        _dl_series = bangumi.series
        _dl_title = _dl_series.canonical_title if _dl_series is not None else ""
        _dl_season = _dl_series.season if _dl_series is not None else 1
        _dl_root = _dl_series.root_path if _dl_series is not None else None
        from pathlib import PurePosixPath
        _dl_full = (
            bangumi.path_override
            or (str(PurePosixPath(_dl_root) / f"Season {_dl_season}") if _dl_root else None)
        )
        save_path = _dl_full or gen_save_path(
            settings.downloader.path, _dl_title, _dl_season,
        )

        # --- Phase 2: NETWORK I/O (downloader call, no DB transaction) ---
        urls = [t.url for t in new_torrents]
        await downloader.add_torrents(
            urls=urls,
            save_path=save_path,
            torrent_files=None,
        )

        # --- Phase 3: SHORT write transaction (persist results) ---
        inserted_count = await torrent_repo.add_all_or_ignore(new_torrents)
        logger.debug(f"[Engine] download_bangumi: inserted {inserted_count}/{len(new_torrents)} torrents")

        for torrent in new_torrents:
            if torrent.hash:
                await torrent_repo.mark_downloaded_by_hash(
                    torrent.hash, bangumi.id, save_path
                )

        await bangumi_repo.update_simple(bangumi.id, {"eps_collect": True})

        await session.commit()

        return {
            "status": True,
            "message": f"Downloaded {len(new_torrents)} torrents",
            "count": len(new_torrents),
        }
