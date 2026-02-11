"""Season Collector Service - Async bangumi collection and subscription."""

import asyncio
import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from module.conf import settings
from module.conf.const import MIKAN_SEASON_RSS_PATTERN
from module.domain.models.bangumi import Bangumi
from module.domain.models.torrent import Torrent
from module.domain.value_objects import ResponseModel, gen_save_path
from module.repositories.bangumi import BangumiRepository
from module.repositories.rss import RSSRepository
from module.repositories.torrent import TorrentRepository
from module.services.downloader.interface import DownloaderProtocol
from module.services.rss_engine import RSSEngine

logger = logging.getLogger(__name__)


def _is_mikan_season_rss(rss_link: str) -> bool:
    """Check if the RSS link is a Mikan season-specific RSS.

    A season-specific RSS has both bangumiId and subgroupid parameters,
    which limits results to a specific season from a specific subgroup.

    Args:
        rss_link: The RSS link to check.

    Returns:
        True if it's a Mikan season-specific RSS link.
    """
    if not rss_link:
        return False
    return bool(MIKAN_SEASON_RSS_PATTERN.search(rss_link))


class SeasonCollectorService:
    """Service for collecting full seasons and managing subscriptions."""

    @staticmethod
    async def collect_season(
        session: AsyncSession,
        downloader: DownloaderProtocol,
        bangumi: Bangumi,
        link: Optional[str] = None,
    ) -> ResponseModel:
        """Collect all episodes for a bangumi season.

        Args:
            session: Async database session
            downloader: Downloader client
            bangumi: Bangumi to collect episodes for
            link: Optional direct RSS link (if None, uses SearchTorrent)

        Returns:
            ResponseModel with collection status
        """
        logger.info(
            f"Start collecting {bangumi.official_title} Season {bangumi.season}..."
        )

        bangumi_repo = BangumiRepository(session)
        torrent_repo = TorrentRepository(session)

        def _fetch_torrents():
            from module.searcher import SearchTorrent

            with SearchTorrent() as st:
                if not link:
                    return st.search_season(bangumi)
                else:
                    return st.get_torrents(link, bangumi.filter.replace(",", "|"))

        legacy_torrents = await asyncio.to_thread(_fetch_torrents)

        torrents = [
            Torrent(
                name=t.name,
                url=t.url,
                homepage=t.homepage,
                hash=t.hash,
                bangumi_id=bangumi.id,
                rss_id=bangumi.rss_id,
            )
            for t in legacy_torrents
        ]

        # Use hash-based deduplication to prevent duplicate torrents (against database)
        if torrents:
            hashes = [t.hash for t in torrents if t.hash]
            new_hashes = await torrent_repo.check_new_by_hash(hashes, bangumi.id)
            new_torrents = [t for t in torrents if t.hash in new_hashes]
        else:
            new_torrents = []

        if not new_torrents:
            logger.info(
                f"No new torrents for {bangumi.official_title} (all duplicates filtered by database)."
            )
            return ResponseModel(
                status=False,
                status_code=404,
                msg_en=f"No new episodes found for {bangumi.official_title}.",
                msg_zh=f"{bangumi.official_title} 没有找到新剧集。",
            )

        # Pre-filter against downloader existing hashes
        already_in_qb_torrents = []
        qb_torrents = await downloader.torrents_info()
        qb_existing_hashes = {t.hash.lower() for t in qb_torrents if t.hash}

        if qb_existing_hashes:
            truly_new_torrents = []
            for t in new_torrents:
                if t.hash and t.hash.lower() in qb_existing_hashes:
                    # Already in downloader - mark as downloaded for DB sync
                    t.downloaded = True
                    already_in_qb_torrents.append(t)
                else:
                    truly_new_torrents.append(t)

            if already_in_qb_torrents:
                logger.info(
                    f"[Collector] Found {len(already_in_qb_torrents)} torrents already in downloader "
                    f"for {bangumi.official_title}, will sync to database"
                )
            new_torrents = truly_new_torrents

        if not new_torrents:
            # All torrents already exist in downloader
            # Add them to database for tracking, mark as collected
            logger.info(
                f"All episodes for {bangumi.official_title} already in downloader."
            )
            bangumi.eps_collect = True
            await bangumi_repo.update_simple(bangumi.id, {"eps_collect": True})
            await session.flush()

            if already_in_qb_torrents:
                await torrent_repo.add_all_or_ignore(already_in_qb_torrents)
                await session.flush()
                logger.info(
                    f"[Collector] Synced {len(already_in_qb_torrents)} existing torrents to database "
                    f"for {bangumi.official_title}"
                )

            await session.commit()
            return ResponseModel(
                status=True,
                status_code=200,
                msg_en=f"All episodes for {bangumi.official_title} already in download client.",
                msg_zh=f"{bangumi.official_title} 的所有剧集已在下载客户端中。",
            )

        all_torrents_to_add = new_torrents + already_in_qb_torrents
        await torrent_repo.add_all_or_ignore(all_torrents_to_add)

        save_path = bangumi.save_path or gen_save_path(
            settings.downloader.path, bangumi.official_title, bangumi.season,
        )

        await session.commit()

        # --- Phase 2: NETWORK I/O (no DB transaction held) ---
        successfully_added_hashes: list[str] = []

        try:
            urls = [t.url for t in new_torrents]
            success = await downloader.add_torrents(
                urls=urls,
                save_path=save_path,
                torrent_files=None,
            )

            if success:
                logger.info(
                    f"Collections of {bangumi.official_title} Season {bangumi.season} completed."
                )
                for torrent in new_torrents:
                    if torrent.hash:
                        successfully_added_hashes.append(torrent.hash)

                # --- Phase 3: SHORT write transaction (mark downloaded) ---
                for torrent in new_torrents:
                    if torrent.hash and bangumi.id is not None:
                        await torrent_repo.mark_downloaded_by_hash(
                            torrent.hash, bangumi.id, save_path
                        )

                bangumi.eps_collect = True
                await bangumi_repo.update_simple(bangumi.id, {"eps_collect": True})
                await session.commit()

                return ResponseModel(
                    status=True,
                    status_code=200,
                    msg_en=f"Collections of {bangumi.official_title} Season {bangumi.season} completed.",
                    msg_zh=f"收集 {bangumi.official_title} 第 {bangumi.season} 季完成。",
                )
            else:
                logger.warning(
                    f"Already collected {bangumi.official_title} Season {bangumi.season}."
                )
                return ResponseModel(
                    status=False,
                    status_code=409,
                    msg_en=f"Collection of {bangumi.official_title} Season {bangumi.season} failed.",
                    msg_zh=f"收集 {bangumi.official_title} 第 {bangumi.season} 季失败, 种子已经添加。",
                )

        except Exception as e:
            logger.error(f"[Collector] Collection failed: {e}")

            if successfully_added_hashes:
                logger.warning(
                    f"[Collector] Rolling back - removing {len(successfully_added_hashes)} torrents from downloader"
                )
                try:
                    await downloader.torrents_delete(successfully_added_hashes, delete_files=True)
                except Exception as cleanup_error:
                    logger.error(f"[Collector] Failed to cleanup downloader: {cleanup_error}")

            await session.rollback()

            raise

    @staticmethod
    async def subscribe_season(
        session: AsyncSession,
        downloader: DownloaderProtocol,
        data: Bangumi,
        parser: str = "mikan",
        delete_files: bool = False,
    ) -> ResponseModel:
        """Subscribe to a single bangumi.

        For non-aggregate RSS, this method handles single bangumi recreation:
        - Deletes existing bangumi from this RSS (typically just 1)
        - Deletes corresponding torrents from downloader
        - Inserts the new bangumi
        - Downloads torrents

        Args:
            session: Async database session
            downloader: Downloader client
            data: Bangumi object to subscribe
            parser: Parser type (default: "mikan")
            delete_files: If True, delete downloaded files when removing old torrents.
                         If False (default), only remove torrents but keep files.

        Returns:
            ResponseModel with subscription status
        """
        bangumi_repo = BangumiRepository(session)
        torrent_repo = TorrentRepository(session)
        rss_repo = RSSRepository(session)

        successfully_added_hashes: list[str] = []

        try:
            data.added = True
            data.eps_collect = True

            # FAIL-FAST: Handle RSS operations BEFORE any deletion
            # This prevents data loss if RSS operations fail
            if not data.rss_id:
                # Check if an RSS with this URL already exists (might have bangumi)
                all_rss = await rss_repo.get_all()
                existing_rss_item = None
                for rss_item in all_rss:
                    if rss_item.url == data.rss_link:
                        existing_rss_item = rss_item
                        data.rss_id = rss_item.id
                        logger.debug(f"[Collector] Found existing RSS with ID {data.rss_id}")
                        break

                # If no existing RSS, create it
                if not existing_rss_item:
                    # Add the RSS feed (can fail - better to fail before deletion)
                    new_rss = await rss_repo.create({
                        "url": data.rss_link,
                        "name": data.official_title,
                        "aggregate": False,
                        "parser": parser,
                        "enabled": True,
                    })
                    data.rss_id = new_rss.id
                    await session.flush()
                    logger.debug(f"[Collector] Created new RSS with ID {data.rss_id}")

            # Check if there's a duplicate from a DIFFERENT RSS source
            # This validation happens BEFORE deletion to prevent conflicts
            group_name = data.group_name if data.group_name else "Unknown"
            existing_active = await bangumi_repo.get_by_composite_key(
                official_title=data.official_title,
                season=data.season,
                group_name=group_name,
            )

            if existing_active and existing_active.rss_id != data.rss_id:
                # Different RSS source - this is a conflict
                existing_rss = (
                    await rss_repo.get_by_id(existing_active.rss_id)
                    if existing_active.rss_id
                    else None
                )
                existing_rss_url = existing_rss.url if existing_rss else None
                logger.warning(
                    f"[Collector] Bangumi already subscribed from different RSS: "
                    f"official_title='{data.official_title}', season={data.season}, group='{group_name}' "
                    f"(existing RSS ID: {existing_active.rss_id}, new RSS ID: {data.rss_id})"
                )
                raise ValueError(
                    f"Bangumi '{data.official_title}' (group: {group_name}) is already subscribed "
                    f"from another RSS source (ID: {existing_active.rss_id}). Delete the existing subscription first."
                )

            hashes_to_delete_from_downloader: list[tuple[list[str], str]] = []

            if data.rss_id:
                await rss_repo.set_status(data.rss_id, "Recreating")
                await session.flush()

                existing_bangumi = await bangumi_repo.get_by_rss(data.rss_id)
                if existing_bangumi:
                    logger.info(
                        f"[Collector] Deleting {len(existing_bangumi)} existing bangumi "
                        f"from RSS ID {data.rss_id} before inserting: {data.official_title}"
                    )
                    for bangumi in existing_bangumi:
                        db_torrents = await torrent_repo.get_by_bangumi(bangumi.id)
                        if db_torrents:
                            hash_list = [t.hash for t in db_torrents if t.hash]
                            if hash_list:
                                hashes_to_delete_from_downloader.append(
                                    (hash_list, bangumi.official_title)
                                )
                    bangumi_ids = [b.id for b in existing_bangumi]
                    await bangumi_repo.delete_many(bangumi_ids)

            save_path = gen_save_path(
                settings.downloader.path, data.official_title, data.season,
                getattr(data, "year", None),
            )
            created_bangumi = await bangumi_repo.create({
                "official_title": data.official_title,
                "title_raw": data.title_raw,
                "season": data.season,
                "season_raw": data.season_raw,
                "group_name": data.group_name or "Unknown",
                "dpi": data.dpi,
                "source": data.source,
                "subtitle": data.subtitle,
                "rss_link": data.rss_link,
                "rss_id": data.rss_id,
                "poster_link": data.poster_link or "",
                "filter": data.filter or "",
                "eps_collect": True,
                "offset": data.offset,
                "added": True,
                "deleted": False,
                "pending_review": False,
                "save_path": save_path,
            })

            await session.commit()
            logger.info(
                f"[Collector] Successfully committed bangumi for {data.official_title} "
                f"(RSS ID: {data.rss_id})"
            )

            # --- Phase 2: NETWORK I/O (delete old + download new, no DB transaction held) ---
            for hash_list, title in hashes_to_delete_from_downloader:
                await downloader.torrents_delete(
                    hash_list, delete_files=delete_files
                )
                logger.info(
                    f"[Collector] Deleted {len(hash_list)} torrents for {title} "
                    f"(delete_files={delete_files})"
                )

            successfully_added_hashes: list[str] = []
            result = await RSSEngine.download_bangumi(
                session, downloader, created_bangumi.id
            )

            # Track hashes of torrents added by download_bangumi
            if isinstance(result, dict) and result.get("count", 0) > 0:
                db_torrents = await torrent_repo.get_by_bangumi(created_bangumi.id)
                if db_torrents:
                    successfully_added_hashes = [t.hash for t in db_torrents if t.hash and t.downloaded]

            # If all torrents were filtered out, set pending_review
            if (
                isinstance(result, dict)
                and not result.get("status")
                and result.get("count") == 0
                and "filtered out" in result.get("message", "").lower()
            ):
                # Mark bangumi as pending review since all torrents were filtered
                await bangumi_repo.update_pending_review(
                    created_bangumi.id, True, data.filter
                )
                await session.commit()
                logger.info(
                    f"[Collector] Bangumi {data.official_title} set to pending review "
                    f"(all torrents filtered by: {data.filter})"
                )

            if data.rss_id:
                await rss_repo.set_status(data.rss_id, "Success")
                await session.commit()

            # Convert dict result to ResponseModel if needed
            if isinstance(result, dict):
                return ResponseModel(
                    status=result.get("status", False),
                    status_code=200 if result.get("status") else 406,
                    msg_en=result.get("message", ""),
                    msg_zh=result.get("message", ""),
                )
            return result

        except Exception as e:
            logger.error(f"[Collector] Subscription failed: {e}")

            # COMPENSATE: Remove torrents from downloader first
            if successfully_added_hashes:
                logger.warning(
                    f"[Collector] Rolling back - removing {len(successfully_added_hashes)} torrents from downloader"
                )
                try:
                    await downloader.torrents_delete(successfully_added_hashes, delete_files=True)
                except Exception as cleanup_error:
                    logger.error(f"[Collector] Failed to cleanup downloader: {cleanup_error}")

            # Then rollback database
            await session.rollback()

            if data.rss_id:
                try:
                    await rss_repo.set_status(data.rss_id, "Error")
                    await session.commit()
                except Exception as rss_err:
                    logger.warning(f"[Collector] Failed to set RSS status to Error: {rss_err}")
            logger.error(
                f"[Collector] Failed to subscribe bangumi {data.official_title}: {e}. "
                f"All changes rolled back."
            )
            raise

    @staticmethod
    async def subscribe_batch(
        session: AsyncSession,
        downloader: DownloaderProtocol,
        bangumi_list: list[Bangumi],
        rss_id: int,
        parser: str = "mikan",
        delete_files: bool = False,
    ) -> ResponseModel:
        """Subscribe to multiple bangumi in a single atomic transaction.

        This method is designed for recreation scenarios where multiple bangumi
        need to be subscribed from a single RSS feed. It:
        1. Deletes all existing bangumi from the RSS ID ONCE
        2. Deletes corresponding torrents from downloader
        3. Inserts all new bangumi in a single transaction
        4. Downloads torrents for each bangumi

        Args:
            session: Async database session
            downloader: Downloader client
            bangumi_list: List of Bangumi objects to subscribe
            rss_id: The RSS ID these bangumi belong to
            parser: Parser type (default: "mikan")
            delete_files: If True, delete downloaded files when removing old torrents.
                         If False (default), only remove torrents but keep files.

        Returns:
            ResponseModel with success/failure counts
        """
        if not bangumi_list:
            return ResponseModel(
                status=False,
                status_code=400,
                msg_en="No bangumi provided for batch subscription.",
                msg_zh="未提供任何番剧进行批量订阅。",
            )

        bangumi_repo = BangumiRepository(session)
        torrent_repo = TorrentRepository(session)
        rss_repo = RSSRepository(session)

        successfully_added_hashes: list[str] = []

        try:
            await rss_repo.set_status(rss_id, "Recreating")
            await session.flush()

            hashes_to_delete_from_downloader: list[tuple[list[str], str]] = []

            existing_bangumi = await bangumi_repo.get_by_rss(rss_id)
            if existing_bangumi:
                logger.info(
                    f"[Collector] Batch recreation: deleting ALL {len(existing_bangumi)} existing bangumi "
                    f"from RSS ID {rss_id} before inserting {len(bangumi_list)} new ones"
                )
                for bangumi in existing_bangumi:
                    db_torrents = await torrent_repo.get_by_bangumi(bangumi.id)
                    if db_torrents:
                        hash_list = [t.hash for t in db_torrents if t.hash]
                        if hash_list:
                            hashes_to_delete_from_downloader.append(
                                (hash_list, bangumi.official_title)
                            )
                bangumi_ids = [b.id for b in existing_bangumi]
                deleted_count = await bangumi_repo.delete_many(bangumi_ids)
                logger.info(f"[Collector] Deleted {deleted_count} bangumi for batch recreation")

            success_count = 0
            failed_titles = []

            for data in bangumi_list:
                try:
                    data.added = True
                    data.eps_collect = True
                    data.rss_id = rss_id

                    save_path = gen_save_path(
                        settings.downloader.path, data.official_title, data.season,
                        getattr(data, "year", None),
                    )
                    await bangumi_repo.create({
                        "official_title": data.official_title,
                        "title_raw": data.title_raw,
                        "season": data.season,
                        "season_raw": data.season_raw,
                        "group_name": data.group_name or "Unknown",
                        "dpi": data.dpi,
                        "source": data.source,
                        "subtitle": data.subtitle,
                        "rss_link": data.rss_link,
                        "rss_id": rss_id,
                        "poster_link": data.poster_link or "",
                        "filter": data.filter or "",
                        "eps_collect": True,
                        "offset": data.offset,
                        "added": True,
                        "deleted": False,
                        "pending_review": False,
                        "save_path": save_path,
                    })
                    success_count += 1
                    logger.debug(f"[Collector] Batch insert: {data.official_title}")
                except Exception as e:
                    logger.error(f"[Collector] Failed to insert {data.official_title}: {e}")
                    failed_titles.append(data.official_title)

            await session.commit()
            logger.info(
                f"[Collector] Batch recreation committed: {success_count}/{len(bangumi_list)} bangumi "
                f"for RSS ID {rss_id}"
            )

            # --- Phase 2: NETWORK I/O (delete old torrents from downloader) ---
            for hash_list, title in hashes_to_delete_from_downloader:
                await downloader.torrents_delete(
                    hash_list, delete_files=delete_files
                )
                logger.info(
                    f"[Collector] Deleted {len(hash_list)} torrents for {title} "
                    f"(delete_files={delete_files})"
                )

            all_bangumi = await bangumi_repo.get_by_rss(rss_id)
            download_results = []

            for bangumi in all_bangumi:
                if bangumi.official_title not in failed_titles:
                    try:
                        result = await RSSEngine.download_bangumi(
                            session, downloader, bangumi.id
                        )
                        download_results.append((bangumi.official_title, result))

                        # Track hashes of torrents added by download_bangumi
                        if isinstance(result, dict) and result.get("count", 0) > 0:
                            db_torrents = await torrent_repo.get_by_bangumi(bangumi.id)
                            if db_torrents:
                                successfully_added_hashes.extend([t.hash for t in db_torrents if t.hash and t.downloaded])

                        # If all torrents were filtered out, set pending_review
                        if (
                            isinstance(result, dict)
                            and not result.get("status")
                            and result.get("count") == 0
                            and "filtered out" in result.get("message", "").lower()
                        ):
                            await bangumi_repo.update_pending_review(
                                bangumi.id, True, bangumi.filter
                            )
                            await session.commit()
                            logger.info(
                                f"[Collector] Bangumi {bangumi.official_title} set to pending review "
                                f"(all torrents filtered by: {bangumi.filter})"
                            )
                    except Exception as e:
                        logger.error(
                            f"[Collector] Failed to download torrents for {bangumi.official_title}: {e}"
                        )

            await rss_repo.set_status(rss_id, "Success")
            await session.commit()

            if success_count == len(bangumi_list):
                return ResponseModel(
                    status=True,
                    status_code=200,
                    msg_en=f"Successfully subscribed {success_count} bangumi.",
                    msg_zh=f"成功订阅 {success_count} 个番剧。",
                )
            elif success_count > 0:
                return ResponseModel(
                    status=True,
                    status_code=200,
                    msg_en=f"Subscribed {success_count}/{len(bangumi_list)} bangumi. Failed: {', '.join(failed_titles)}",
                    msg_zh=f"订阅了 {success_count}/{len(bangumi_list)} 个番剧。失败：{', '.join(failed_titles)}",
                )
            else:
                return ResponseModel(
                    status=False,
                    status_code=500,
                    msg_en=f"Failed to subscribe any bangumi.",
                    msg_zh=f"未能订阅任何番剧。",
                )

        except Exception as e:
            logger.error(f"[Collector] Batch subscription failed: {e}")

            # COMPENSATE: Remove torrents from downloader first
            if successfully_added_hashes:
                logger.warning(
                    f"[Collector] Rolling back - removing {len(successfully_added_hashes)} torrents from downloader"
                )
                try:
                    await downloader.torrents_delete(successfully_added_hashes, delete_files=True)
                except Exception as cleanup_error:
                    logger.error(f"[Collector] Failed to cleanup downloader: {cleanup_error}")

            # Then rollback database
            await session.rollback()

            try:
                await rss_repo.set_status(rss_id, "Error")
                await session.commit()
            except Exception as rss_err:
                logger.warning(f"[Collector] Failed to set RSS status to Error: {rss_err}")
            logger.error(f"[Collector] Batch subscription failed: {e}. All changes rolled back.")
            raise
