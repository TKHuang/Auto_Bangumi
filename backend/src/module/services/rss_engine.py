"""RSS Engine Service - Async RSS feed processing with atomic transactions."""

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from module.conf import settings
from module.domain.models.bangumi import Bangumi
from module.domain.models.rss import RSSItem
from module.domain.models.torrent import Torrent
from module.domain.parser.title_parser import TitleParser
from module.network.request_contents import RequestContent
from module.repositories.bangumi import BangumiRepository
from module.repositories.rss import RSSRepository
from module.repositories.torrent import TorrentRepository
from module.services.downloader.interface import DownloaderProtocol

logger = logging.getLogger(__name__)


class RSSEngine:
    """RSS Engine for feed processing and torrent management."""

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
    async def match_torrent_to_bangumi(
        torrent: Torrent, bangumi_repo: BangumiRepository
    ) -> Optional[Bangumi]:
        """Match torrent to bangumi rule with filter logic.

        Args:
            torrent: Torrent to match
            bangumi_repo: Bangumi repository

        Returns:
            Matched Bangumi or None if no match or filtered
        """
        all_bangumi = await bangumi_repo.get_active()

        for bangumi in all_bangumi:
            if bangumi.official_title in torrent.name or bangumi.title_raw in torrent.name:
                torrent.bangumi_id = bangumi.id

                if bangumi.filter == "":
                    return bangumi

                _filter = bangumi.filter.replace(",", "|")
                if re.search(_filter, torrent.name, re.IGNORECASE):
                    logger.debug(
                        f"[Engine] Torrent {torrent.name} excluded by filter: {bangumi.filter}"
                    )
                    return None
                else:
                    return bangumi

        return None

    @staticmethod
    async def refresh_rss(
        session: AsyncSession,
        downloader: DownloaderProtocol,
        rss_id: Optional[int] = None,
    ) -> None:
        """Refresh RSS feeds and download matched torrents.

        Args:
            session: Async database session
            downloader: Downloader client
            rss_id: Optional RSS ID (None = refresh all enabled)
        """
        rss_repo = RSSRepository(session)
        bangumi_repo = BangumiRepository(session)
        torrent_repo = TorrentRepository(session)

        if rss_id:
            rss_item = await rss_repo.get_by_id(rss_id)
            rss_items = [rss_item] if rss_item else []
        else:
            rss_items = await rss_repo.get_enabled()

        logger.debug(f"[Engine] Processing {len(rss_items)} RSS items")

        for rss_item in rss_items:
            # Fix: Skip if recreating (concurrency gate)
            if rss_item.last_status == "Recreating":
                logger.debug(f"[Engine] Skipping RSS {rss_item.name} - recreation in progress")
                continue

            try:
                new_torrents = await RSSEngine.parse_rss_feed(rss_item.url)

                matched_torrents = []
                for torrent in new_torrents:
                    torrent.rss_id = rss_item.id
                    matched_bangumi = await RSSEngine.match_torrent_to_bangumi(
                        torrent, bangumi_repo
                    )
                    if matched_bangumi:
                        matched_torrents.append(torrent)
                    else:
                        logger.debug(
                            f"[Engine] Skip torrent {torrent.name} - no matching bangumi"
                        )

                if matched_torrents:
                    # Fix: Use idempotent bulk insert
                    inserted_count = await torrent_repo.add_all_or_ignore(matched_torrents)
                    logger.debug(f"[Engine] Inserted {inserted_count} new torrents")

                    if inserted_count == 0:
                        logger.debug("[Engine] No new torrents to download, skipping")
                        continue

                    for torrent in matched_torrents:
                        # Skip torrents already downloaded (existed in DB before this cycle)
                        db_torrent = await torrent_repo.get_by_hash(torrent.hash)
                        if db_torrent and db_torrent.downloaded:
                            logger.debug(
                                f"[Engine] Skip already-downloaded torrent: {torrent.name}"
                            )
                            continue

                        matched_bangumi = await RSSEngine.match_torrent_to_bangumi(
                            torrent, bangumi_repo
                        )
                        if matched_bangumi:
                            urls = [torrent.url]
                            success = await downloader.add_torrents(
                                urls=urls,
                                save_path=matched_bangumi.save_path or "",
                                torrent_files=None,
                            )
                            if success:
                                logger.debug(
                                    f"[Engine] Added torrent {torrent.name} to downloader"
                                )
                                if db_torrent:
                                    await torrent_repo.mark_downloaded(db_torrent.id)

                await rss_repo.update_status(rss_item.id, "Success", None)

            except Exception as e:
                logger.error(f"[Engine] Refresh RSS {rss_item.name} failed: {e}")
                await rss_repo.update_status(rss_item.id, "Error", str(e))

        await session.commit()

    @staticmethod
    async def refresh_all_rss(
        session: AsyncSession, downloader: DownloaderProtocol
    ) -> None:
        """Refresh all enabled RSS feeds.

        Args:
            session: Async database session
            downloader: Downloader client
        """
        await RSSEngine.refresh_rss(session, downloader, rss_id=None)

    @staticmethod
    async def create_bangumi_from_torrent(
        session: AsyncSession,
        downloader: DownloaderProtocol,
        torrent_id: int,
    ) -> dict:
        """Create bangumi rule from torrent (subscribe/analyze).

        Args:
            session: Async database session
            downloader: Downloader client
            torrent_id: Torrent ID to create bangumi from

        Returns:
            Result dict with status and message
        """
        torrent_repo = TorrentRepository(session)
        bangumi_repo = BangumiRepository(session)
        rss_repo = RSSRepository(session)

        torrent = await session.get(Torrent, torrent_id)
        if not torrent:
            return {
                "status": False,
                "message": "Torrent not found",
            }

        if not torrent.rss_id:
            return {
                "status": False,
                "message": "Torrent is not from an RSS feed",
            }

        rss = await rss_repo.get_by_id(torrent.rss_id)
        if not rss:
            return {
                "status": False,
                "message": "Associated RSS feed not found",
            }

        parser = TitleParser()
        bangumi_data = parser.raw_parser(torrent.name)

        if not bangumi_data:
            return {
                "status": False,
                "message": "Failed to parse torrent name",
            }

        existing = await bangumi_repo.get_by_composite_key(
            bangumi_data.official_title,
            bangumi_data.season,
            bangumi_data.group_name,
        )

        if existing:
            return {
                "status": False,
                "message": f"Bangumi already exists: {existing.official_title}",
            }

        bangumi_data.rss_link = rss.url
        bangumi_data.rss_id = rss.id

        created_bangumi = await bangumi_repo.create({
            "official_title": bangumi_data.official_title,
            "title_raw": bangumi_data.title_raw,
            "season": bangumi_data.season,
            "season_raw": bangumi_data.season_raw,
            "group_name": bangumi_data.group_name,
            "dpi": bangumi_data.dpi,
            "source": bangumi_data.source,
            "subtitle": bangumi_data.subtitle,
            "rss_link": bangumi_data.rss_link,
            "rss_id": bangumi_data.rss_id,
            "poster_link": bangumi_data.poster_link or "",
            "filter": bangumi_data.filter or "",
            "eps_collect": bangumi_data.eps_collect,
            "offset": bangumi_data.offset,
            "added": False,
            "deleted": False,
            "pending_review": False,
        })

        await session.flush()

        torrent.bangumi_id = created_bangumi.id
        await session.flush()

        urls = [torrent.url]
        await downloader.add_torrents(
            urls=urls,
            save_path=created_bangumi.save_path or "",
            torrent_files=None,
        )

        await torrent_repo.mark_downloaded(torrent.id)

        await session.commit()

        return {
            "status": True,
            "message": f"Successfully created bangumi: {created_bangumi.official_title}",
            "bangumi_id": created_bangumi.id,
        }

    @staticmethod
    async def download_bangumi(
        session: AsyncSession,
        downloader: DownloaderProtocol,
        bangumi_id: int,
    ) -> dict:
        """Download all episodes for bangumi (collection/backfill).

        Args:
            session: Async database session
            downloader: Downloader client
            bangumi_id: Bangumi ID to download

        Returns:
            Result dict with status and count
        """
        bangumi_repo = BangumiRepository(session)
        torrent_repo = TorrentRepository(session)

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

        filtered_torrents = []
        if bangumi.filter:
            _filter = bangumi.filter.replace(",", "|")
            for torrent in all_torrents:
                if not re.search(_filter, torrent.name, re.IGNORECASE):
                    filtered_torrents.append(torrent)
        else:
            filtered_torrents = all_torrents

        if not filtered_torrents:
            return {
                "status": False,
                "message": "All torrents filtered out",
                "count": 0,
            }

        new_torrents = []
        for torrent in filtered_torrents:
            torrent.bangumi_id = bangumi.id
            torrent.rss_id = bangumi.rss_id

            if torrent.hash:
                new_hashes = await torrent_repo.check_new_by_hash(
                    [torrent.hash], bangumi.id
                )
                if torrent.hash in new_hashes:
                    new_torrents.append(torrent)
            else:
                new_torrents.append(torrent)

        if not new_torrents:
            return {
                "status": True,
                "message": "No new torrents to download",
                "count": 0,
            }

        inserted_count = await torrent_repo.add_all_or_ignore(new_torrents)
        logger.debug(f"[Engine] download_bangumi: inserted {inserted_count}/{len(new_torrents)} torrents")

        await session.flush()

        urls = [t.url for t in new_torrents]
        await downloader.add_torrents(
            urls=urls,
            save_path=bangumi.save_path or "",
            torrent_files=None,
        )

        for torrent in new_torrents:
            db_torrent = await torrent_repo.get_by_hash(torrent.hash)
            if db_torrent:
                await torrent_repo.mark_downloaded(db_torrent.id)

        await session.commit()

        return {
            "status": True,
            "message": f"Downloaded {len(new_torrents)} torrents",
            "count": len(new_torrents),
        }
