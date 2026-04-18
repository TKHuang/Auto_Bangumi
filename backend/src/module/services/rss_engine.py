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
from module.domain.value_objects import BangumiParsingError, gen_save_path
from module.mikan.parser import extract_mikan_ids_from_rss
from module.network.request_contents import RequestContent
from module.repositories.bangumi import BangumiRepository
from module.repositories.rss import RSSRepository
from module.repositories.torrent import TorrentRepository
from module.services.downloader.interface import DownloaderProtocol
from module.services.identity_resolver import resolve_series_for_rss

logger = logging.getLogger(__name__)

_FILTERED = object()


def _extract_mikan_bangumi_id(url: str) -> str | None:
    if not url:
        return None
    match = re.search(r"bangumiId=(\d+)", url)
    return match.group(1) if match else None


def _is_cross_season(source_rss_url: str, bangumi_rss_link: str) -> bool:
    """True when source RSS and bangumi RSS are both Mikan season feeds
    with different bangumiIds (i.e. different seasons of the same show)."""
    source_id = _extract_mikan_bangumi_id(source_rss_url)
    target_id = _extract_mikan_bangumi_id(
        bangumi_rss_link.split(",")[0] if bangumi_rss_link else ""
    )
    return bool(source_id and target_id and source_id != target_id)


def _match_torrent_in_list(
    torrent: Torrent, bangumi_list: list[Bangumi]
) -> Optional[Bangumi]:
    """In-memory torrent-to-bangumi matching (no DB call)."""
    for bangumi in bangumi_list:
        _canonical = bangumi.series.canonical_title if bangumi.series is not None else ""
        _title_raw = getattr(bangumi, "title_raw", None)
        if _canonical and (_canonical in torrent.name or (_title_raw and _title_raw in torrent.name)):
            torrent.bangumi_id = bangumi.id
            if not bangumi.filter:
                return bangumi
            _filter = bangumi.filter.replace(",", "|")
            if re.search(_filter, torrent.name, re.IGNORECASE):
                return None
            return bangumi
    return None


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
    ) -> Optional[Bangumi] | object:
        """Match torrent to bangumi rule with filter logic.

        Returns:
            Matched Bangumi, _FILTERED if matched but excluded by filter, or None if no match.
        """
        all_bangumi = await bangumi_repo.get_active(enabled_only=True)

        for bangumi in all_bangumi:
            _canonical = bangumi.series.canonical_title if bangumi.series is not None else ""
            if _canonical and _canonical in torrent.name:
                torrent.bangumi_id = bangumi.id

                if bangumi.filter == "":
                    return bangumi

                _filter = bangumi.filter.replace(",", "|")
                if re.search(_filter, torrent.name, re.IGNORECASE):
                    logger.debug(
                        f"[Engine] Torrent {torrent.name} excluded by filter: {bangumi.filter}"
                    )
                    return _FILTERED
                else:
                    return bangumi

        return None

    @staticmethod
    def _torrent_excluded_by_filter(torrent_name: str, bangumi_filter: str) -> bool:
        if not bangumi_filter:
            return False
        pattern = bangumi_filter.replace(",", "|")
        return bool(re.search(pattern, torrent_name, re.IGNORECASE))

    @staticmethod
    async def _auto_create_bangumi(
        torrent: Torrent,
        rss_item,
        bangumi_repo: BangumiRepository,
        session: AsyncSession,
        auto_created_keys: set[tuple[str, int, str]],
        newly_created_ids: set[int],
    ) -> Optional[Bangumi]:
        try:
            parser = TitleParser()
            bangumi_data = parser.raw_parser(torrent.name)
        except BangumiParsingError:
            logger.debug(f"[Engine] Cannot parse title for auto-create: {torrent.name}")
            return None

        if not bangumi_data:
            logger.debug(f"[Engine] Cannot parse title for auto-create: {torrent.name}")
            return None

        group_name = bangumi_data.group_name or "Unknown"
        composite_key = (bangumi_data.official_title, bangumi_data.season, group_name)

        # Mikan enrichment: fetch poster + canonical title from episode page.
        parsed_rss_link = bangumi_data.rss_link
        if torrent.homepage and rss_item.parser == "mikan":
            try:
                result = await asyncio.to_thread(parser.mikan_parser_with_rss, torrent.homepage)
                if result.poster_link:
                    bangumi_data.poster_link = result.poster_link
                if result.official_title:
                    bangumi_data.official_title = re.sub(r"[/:.\\]", " ", result.official_title)
                if result.season_rss_link:
                    bangumi_data.rss_link = result.season_rss_link
                    parsed_rss_link = bangumi_data.rss_link
            except Exception as e:
                logger.debug(f"[Engine] Mikan enrichment failed for {torrent.name}: {e}")

        # Resolve series identity (or find existing bangumi) via series-based keys.
        effective_rss_link = parsed_rss_link or rss_item.url
        mikan_bangumi_id, mikan_subgroup_id = extract_mikan_ids_from_rss(effective_rss_link)

        # Check in-memory cache first (avoids repeated DB round trips for same key).
        if composite_key in auto_created_keys:
            # Cache says we created/found a bangumi for this key — look it up.
            resolved = await resolve_series_for_rss(
                session,
                rss_link=effective_rss_link,
                parsed_title=bangumi_data.official_title,
                parsed_season=bangumi_data.season,
                parsed_poster=getattr(bangumi_data, "poster_link", None),
            )
            existing = (
                await bangumi_repo.get_by_series_and_subgroup(
                    resolved.series.id, mikan_subgroup_id
                )
                if mikan_subgroup_id is not None
                else await bangumi_repo.get_by_series_and_rss(
                    resolved.series.id, rss_item.id
                )
            )
            if existing:
                if RSSEngine._torrent_excluded_by_filter(torrent.name, existing.filter):
                    logger.debug(
                        f"[Engine] Torrent {torrent.name} excluded by filter: {existing.filter}"
                    )
                    return None
                torrent.bangumi_id = existing.id
                return existing
            auto_created_keys.discard(composite_key)
            logger.debug(f"[Engine] Cached key {composite_key} not in DB, will re-create")

        # Resolve series for new or uncached bangumi.
        resolved = await resolve_series_for_rss(
            session,
            rss_link=effective_rss_link,
            parsed_title=bangumi_data.official_title,
            parsed_season=bangumi_data.season,
            parsed_poster=getattr(bangumi_data, "poster_link", None),
        )

        # Check if bangumi already exists for this series+subgroup/rss.
        existing = (
            await bangumi_repo.get_by_series_and_subgroup(
                resolved.series.id, mikan_subgroup_id
            )
            if mikan_subgroup_id is not None
            else await bangumi_repo.get_by_series_and_rss(
                resolved.series.id, rss_item.id
            )
        )
        if existing:
            auto_created_keys.add(composite_key)
            if RSSEngine._torrent_excluded_by_filter(torrent.name, existing.filter):
                logger.debug(
                    f"[Engine] Torrent {torrent.name} excluded by filter: {existing.filter}"
                )
                return None
            return existing

        bangumi_filter = bangumi_data.filter or ""

        try:
            created = await bangumi_repo.create({
                "series_id": resolved.series.id,
                "mikan_subgroup_id": mikan_subgroup_id,
                "group_name": group_name,
                "dpi": bangumi_data.dpi,
                "source": bangumi_data.source,
                "subtitle": bangumi_data.subtitle,
                "rss_link": effective_rss_link,
                "rss_id": rss_item.id,
                "filter": bangumi_filter,
                "eps_collect": bangumi_data.eps_collect,
                "offset": bangumi_data.offset,
                "added": True,
                "deleted": False,
                "pending_review": False,
                "active": True,
            })
            auto_created_keys.add(composite_key)
            newly_created_ids.add(created.id)
            logger.info(
                f"[Engine] Auto-created bangumi from aggregate RSS: {bangumi_data.official_title} "
                f"S{bangumi_data.season} [{group_name}]"
            )
            if RSSEngine._torrent_excluded_by_filter(torrent.name, bangumi_filter):
                logger.debug(
                    f"[Engine] Torrent {torrent.name} excluded by filter: {bangumi_filter}"
                )
                return None
            return created
        except ValueError:
            auto_created_keys.add(composite_key)
            logger.debug(
                f"[Engine] Bangumi already exists (race): {bangumi_data.official_title}"
            )
            found = (
                await bangumi_repo.get_by_series_and_subgroup(
                    resolved.series.id, mikan_subgroup_id
                )
                if mikan_subgroup_id is not None
                else await bangumi_repo.get_by_series_and_rss(
                    resolved.series.id, rss_item.id
                )
            )
            if found and RSSEngine._torrent_excluded_by_filter(torrent.name, found.filter):
                return None
            return found

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

        # Pre-extract attributes from ORM objects to avoid lazy-load after rollback.
        # After session.rollback(), ORM objects become expired and accessing their
        # attributes triggers lazy-loading which fails outside of greenlet context.
        rss_item_attrs = []
        for item in rss_items:
            rss_item_attrs.append({
                "id": item.id,
                "name": item.name,
                "url": item.url,
                "last_status": item.last_status,
                "aggregate": item.aggregate,
            })

        for rss_attr in rss_item_attrs:
            if rss_attr["last_status"] == "Recreating":
                logger.debug(f"[Engine] Skipping RSS {rss_attr['name']} - recreation in progress")
                continue

            rss_item_name = rss_attr["name"]
            rss_item_id = rss_attr["id"]
            successfully_added_hashes: list[str] = []

            try:
                rss_item = await rss_repo.get_by_id(rss_item_id)
                if not rss_item:
                    logger.warning(f"[Engine] RSS {rss_item_name} (id={rss_item_id}) no longer exists, skipping")
                    continue
                new_torrents = await RSSEngine.parse_rss_feed(rss_attr["url"])

                matched_torrents = []
                auto_created_keys: set[tuple[str, int, str]] = set()
                newly_created_ids: set[int] = set()

                for torrent in new_torrents:
                    torrent.rss_id = rss_item_id
                    match_result = await RSSEngine.match_torrent_to_bangumi(
                        torrent, bangumi_repo
                    )
                    if match_result is _FILTERED:
                        continue
                    elif isinstance(match_result, Bangumi):
                        matched_bangumi = match_result
                        if _is_cross_season(rss_attr["url"], matched_bangumi.rss_link or ""):
                            logger.debug(
                                f"[Engine] Skip {torrent.name} - cross-season RSS mismatch"
                            )
                            continue
                        matched_torrents.append(torrent)
                    elif rss_attr["aggregate"]:
                        created = await RSSEngine._auto_create_bangumi(
                            torrent, rss_item, bangumi_repo, session,
                            auto_created_keys, newly_created_ids,
                        )
                        if created:
                            torrent.bangumi_id = created.id
                            matched_torrents.append(torrent)
                    else:
                        logger.debug(
                            f"[Engine] Skip torrent {torrent.name} - no matching bangumi"
                        )

                # Persist auto-created bangumi BEFORE the backfill loop.
                # download_bangumi may rollback on failure; if the auto-created
                # bangumi are still pending (flushed but not committed), that
                # rollback wipes them, leaving matched_torrents with dangling
                # bangumi_id references that cause FK violations in the final
                # add_all_or_ignore call.
                if newly_created_ids:
                    await session.commit()

                for bangumi_id in newly_created_ids:
                    try:
                        result = await RSSEngine.download_bangumi(
                            session, downloader, bangumi_id
                        )
                        if isinstance(result, dict) and result.get("count", 0) > 0:
                            logger.info(
                                f"[Engine] Backfilled {result['count']} episodes for bangumi {bangumi_id}"
                            )
                        elif (
                            isinstance(result, dict)
                            and not result.get("status")
                            and result.get("count") == 0
                            and "filtered out" in result.get("message", "").lower()
                        ):
                            bangumi = await bangumi_repo.get_by_id(bangumi_id)
                            if bangumi:
                                await bangumi_repo.update_pending_review(
                                    bangumi_id, True, bangumi.filter
                                )
                                _b_title = bangumi.series.canonical_title if bangumi.series is not None else ""
                                logger.info(
                                    f"[Engine] Bangumi {_b_title} set to pending review "
                                    f"(all torrents filtered by: {bangumi.filter})"
                                )
                    except Exception as e:
                        logger.error(f"[Engine] Episode backfill failed for bangumi {bangumi_id}: {e}")
                        await session.rollback()

                if matched_torrents:
                    inserted_count = await torrent_repo.add_all_or_ignore(matched_torrents)
                    logger.debug(f"[Engine] Inserted {inserted_count} new torrents")

                    if inserted_count > 0:
                        torrent_hashes = [t.hash for t in matched_torrents if t.hash]
                        db_torrents_map = await torrent_repo.get_by_hashes(torrent_hashes)
                        all_active_bangumi = await bangumi_repo.get_active(enabled_only=True)

                        # Phase 2: NETWORK — add torrents to downloader, collect results
                        download_results: list[tuple[str, int, str]] = []
                        for torrent in matched_torrents:
                            db_torrent = db_torrents_map.get(torrent.hash)
                            if db_torrent and db_torrent.downloaded:
                                logger.debug(
                                    f"[Engine] Skip already-downloaded torrent: {torrent.name}"
                                )
                                continue

                            matched_bangumi = _match_torrent_in_list(
                                torrent, all_active_bangumi
                            )
                            if matched_bangumi:
                                _m_series = matched_bangumi.series
                                _m_title = _m_series.canonical_title if _m_series is not None else ""
                                _m_season = _m_series.season if _m_series is not None else 1
                                _m_root = _m_series.root_path if _m_series is not None else None
                                from pathlib import PurePosixPath
                                _m_full = (
                                    matched_bangumi.path_override
                                    or (str(PurePosixPath(_m_root) / f"Season {_m_season}") if _m_root else None)
                                )
                                save_path = _m_full or gen_save_path(
                                    settings.downloader.path, _m_title, _m_season,
                                )
                                urls = [torrent.url]
                                success = await downloader.add_torrents(
                                    urls=urls,
                                    save_path=save_path,
                                    torrent_files=None,
                                )
                                if success:
                                    if torrent.hash:
                                        successfully_added_hashes.append(torrent.hash)
                                    logger.debug(
                                        f"[Engine] Added torrent {torrent.name} to downloader"
                                    )
                                    if db_torrent and db_torrent.hash:
                                        download_results.append(
                                            (db_torrent.hash, matched_bangumi.id, save_path)
                                        )

                        # Phase 3: SHORT write — mark all downloaded in one batch
                        for torrent_hash, bangumi_id_val, save_path in download_results:
                            await torrent_repo.mark_downloaded_by_hash(
                                torrent_hash, bangumi_id_val, save_path
                            )

                await rss_repo.update_status(rss_item_id, "Success", None)
                await session.commit()
                logger.debug(f"[Engine] Committed changes for RSS {rss_item_name}")

            except Exception as e:
                logger.error(f"[Engine] Refresh RSS {rss_item_name} failed: {e}")

                if successfully_added_hashes:
                    logger.warning(
                        f"[Engine] Rolling back - removing {len(successfully_added_hashes)} "
                        f"torrents from downloader for RSS {rss_item_name}"
                    )
                    try:
                        await downloader.torrents_delete(successfully_added_hashes, delete_files=True)
                    except Exception as cleanup_error:
                        logger.error(f"[Engine] Failed to cleanup downloader: {cleanup_error}")

                await session.rollback()

                try:
                    await rss_repo.update_status(rss_item_id, "Error", str(e))
                    await session.commit()
                except Exception as status_error:
                    logger.error(f"[Engine] Failed to update RSS error status: {status_error}")
                    await session.rollback()

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

        bangumi_data.rss_link = rss.url
        bangumi_data.rss_id = rss.id

        mikan_bangumi_id, mikan_subgroup_id = extract_mikan_ids_from_rss(rss.url)
        resolved = await resolve_series_for_rss(
            session,
            rss_link=rss.url,
            parsed_title=bangumi_data.official_title,
            parsed_season=bangumi_data.season,
            parsed_poster=getattr(bangumi_data, "poster_link", None),
        )

        existing = (
            await bangumi_repo.get_by_series_and_subgroup(
                resolved.series.id, mikan_subgroup_id
            )
            if mikan_subgroup_id is not None
            else await bangumi_repo.get_by_series_and_rss(
                resolved.series.id, rss.id
            )
        )

        if existing:
            _ex_title = existing.series.canonical_title if existing.series is not None else ""
            return {
                "status": False,
                "message": f"Bangumi already exists: {_ex_title}",
            }

        created_bangumi = await bangumi_repo.create({
            "series_id": resolved.series.id,
            "mikan_subgroup_id": mikan_subgroup_id,
            "group_name": bangumi_data.group_name or "Unknown",
            "dpi": bangumi_data.dpi,
            "source": bangumi_data.source,
            "subtitle": bangumi_data.subtitle,
            "rss_link": bangumi_data.rss_link,
            "rss_id": bangumi_data.rss_id,
            "filter": bangumi_data.filter or "",
            "eps_collect": bangumi_data.eps_collect,
            "offset": bangumi_data.offset,
            "added": False,
            "deleted": False,
            "pending_review": False,
            "active": True,
        })

        await session.flush()

        torrent.bangumi_id = created_bangumi.id
        await session.flush()

        urls = [torrent.url]
        _cr_series = created_bangumi.series
        _cr_title = _cr_series.canonical_title if _cr_series is not None else ""
        _cr_season = _cr_series.season if _cr_series is not None else 1
        _cr_root = _cr_series.root_path if _cr_series is not None else None
        from pathlib import PurePosixPath
        _cr_full = (
            created_bangumi.path_override
            or (str(PurePosixPath(_cr_root) / f"Season {_cr_season}") if _cr_root else None)
        )
        _cr_save_path = _cr_full or gen_save_path(
            settings.downloader.path, _cr_title, _cr_season,
        )
        await downloader.add_torrents(
            urls=urls,
            save_path=_cr_save_path,
            torrent_files=None,
        )

        await torrent_repo.mark_downloaded_by_hash(
            torrent.hash, created_bangumi.id, _cr_save_path
        )

        await session.commit()

        return {
            "status": True,
            "message": f"Successfully created bangumi: {_cr_title}",
            "bangumi_id": created_bangumi.id,
        }

    @staticmethod
    async def download_bangumi(
        session: AsyncSession,
        downloader: DownloaderProtocol,
        bangumi_id: int,
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

        # Title match: when rss_link is an aggregate feed, only keep torrents
        # whose name contains this bangumi's title to avoid cross-contamination.
        _canonical = bangumi.series.canonical_title if bangumi.series is not None else ""
        _title_raw = getattr(bangumi, "title_raw", None)
        title_matched = []
        for torrent in all_torrents:
            if (_canonical and _canonical in torrent.name) or \
               (_title_raw and _title_raw in torrent.name):
                title_matched.append(torrent)
        # If title matching yields nothing, fall back to all (non-aggregate single-bangumi feeds)
        if not title_matched:
            title_matched = all_torrents

        filtered_torrents = []
        if bangumi.filter:
            _filter = bangumi.filter.replace(",", "|")
            for torrent in title_matched:
                if not re.search(_filter, torrent.name, re.IGNORECASE):
                    filtered_torrents.append(torrent)
        else:
            filtered_torrents = title_matched

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

        await session.commit()

        return {
            "status": True,
            "message": f"Downloaded {len(new_torrents)} torrents",
            "count": len(new_torrents),
        }
