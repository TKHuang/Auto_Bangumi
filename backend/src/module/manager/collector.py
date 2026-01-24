import logging
import time
from typing import Dict

from module.conf import settings
from module.conf.const import MIKAN_SEASON_RSS_PATTERN
from module.downloader import DownloadClient
from module.models import Bangumi, ResponseModel
from module.rss import RSSEngine
from module.searcher import SearchTorrent

logger = logging.getLogger(__name__)

# Track RSS recreation deletions to prevent deleting newly inserted bangumi
# Format: {rss_id: deletion_timestamp}
# During recreation loops, only the first subscribe call should delete all bangumi
# Subsequent calls within 10 seconds are part of the same recreation and should skip deletion
_recreation_deletion_tracker: Dict[int, float] = {}
_RECREATION_WINDOW_SECONDS = 10


class SeasonCollector(DownloadClient):
    def collect_season(self, bangumi: Bangumi, link: str = None):
        logger.info(
            f"Start collecting {bangumi.official_title} Season {bangumi.season}..."
        )
        with SearchTorrent() as st, RSSEngine() as engine:
            if not link:
                torrents = st.search_season(bangumi)
            else:
                torrents = st.get_torrents(link, bangumi.filter.replace(",", "|"))

            # Set foreign keys for all level 2 torrents before checking/adding
            for torrent in torrents:
                torrent.bangumi_id = bangumi.id
                if bangumi.rss_id:
                    torrent.rss_id = bangumi.rss_id

            # Use hash-based deduplication to prevent duplicate torrents (against database)
            new_torrents = engine.torrent.check_new_by_hash(torrents)
            if not new_torrents:
                logger.info(
                    f"No new torrents for {bangumi.official_title} (all duplicates filtered by database)."
                )
                return ResponseModel(
                    status=False,
                    status_code=406,
                    msg_en=f"No new episodes found for {bangumi.official_title}.",
                    msg_zh=f"{bangumi.official_title} 没有找到新剧集。",
                )

            # Pre-filter against qBittorrent existing hashes to avoid batch add failures
            # This handles cases where qBittorrent has torrents that aren't in our database
            # (e.g., after database reset while keeping qBittorrent tasks)
            # Track torrents already in qB for database sync
            already_in_qb_torrents = []
            qb_existing_hashes = self.get_existing_hashes()
            if qb_existing_hashes:
                truly_new_torrents = []
                for t in new_torrents:
                    if t.hash in qb_existing_hashes:
                        # Already in qBittorrent - mark as downloaded for DB sync
                        t.downloaded = True
                        already_in_qb_torrents.append(t)
                    else:
                        truly_new_torrents.append(t)
                if already_in_qb_torrents:
                    logger.info(
                        f"[Collector] Found {len(already_in_qb_torrents)} torrents already in qBittorrent "
                        f"for {bangumi.official_title}, will sync to database"
                    )
                new_torrents = truly_new_torrents

            if not new_torrents:
                # All torrents already exist in qBittorrent
                # Add them to database for tracking, mark as collected
                logger.info(
                    f"All episodes for {bangumi.official_title} already in qBittorrent."
                )
                bangumi.eps_collect = True
                if engine.bangumi.update(bangumi):
                    engine.bangumi.add(bangumi)
                # Sync torrents that exist in qB but not in DB
                if already_in_qb_torrents:
                    engine.torrent.add_all(already_in_qb_torrents)
                    logger.info(
                        f"[Collector] Synced {len(already_in_qb_torrents)} existing torrents to database "
                        f"for {bangumi.official_title}"
                    )
                return ResponseModel(
                    status=True,
                    status_code=200,
                    msg_en=f"All episodes for {bangumi.official_title} already in download client.",
                    msg_zh=f"{bangumi.official_title} 的所有剧集已在下载客户端中。",
                )

            if self.add_torrent(new_torrents, bangumi):
                logger.info(
                    f"Collections of {bangumi.official_title} Season {bangumi.season} completed."
                )
                for torrent in new_torrents:
                    torrent.downloaded = True
                bangumi.eps_collect = True
                if engine.bangumi.update(bangumi):
                    engine.bangumi.add(bangumi)
                # Add both newly downloaded and already-in-qB torrents to database
                all_torrents_to_add = new_torrents + already_in_qb_torrents
                engine.torrent.add_all(all_torrents_to_add)
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
                    status_code=406,
                    msg_en=f"Collection of {bangumi.official_title} Season {bangumi.season} failed.",
                    msg_zh=f"收集 {bangumi.official_title} 第 {bangumi.season} 季失败, 种子已经添加。",
                )

    @staticmethod
    def subscribe_season(data: Bangumi, parser: str = "mikan"):
        with RSSEngine() as engine:
            try:
                data.added = True
                data.eps_collect = True

                # FAIL-FAST: Handle RSS operations BEFORE any deletion
                # This prevents data loss if RSS operations fail
                if not data.rss_id:
                    # Check if an RSS with this URL already exists (might have bangumi)
                    all_rss = engine.rss.search_all()
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
                        engine.add_rss(
                            rss_link=data.rss_link,
                            name=data.official_title,
                            aggregate=False,
                            parser=parser,
                        )

                        # Get the RSS ID by searching again
                        all_rss = engine.rss.search_all()
                        for rss_item in all_rss:
                            if rss_item.url == data.rss_link:
                                data.rss_id = rss_item.id
                                logger.debug(f"[Collector] Created new RSS with ID {data.rss_id}")
                                break

                # Check if there's a duplicate from a DIFFERENT RSS source
                # This validation happens BEFORE deletion to prevent conflicts
                group_name = data.group_name if data.group_name else "Unknown"
                existing_active = engine.bangumi.search_by_composite_key(
                    official_title=data.official_title,
                    season=data.season,
                    group_name=group_name,
                )

                if existing_active and existing_active.rss_id != data.rss_id:
                    # Different RSS source - this is a conflict
                    existing_rss = engine.rss.search_id(existing_active.rss_id) if existing_active.rss_id else None
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

                # ATOMIC TRANSACTION: Delete ALL bangumi from this RSS + Insert new bangumi
                # This ensures recreation properly clears ALL old bangumi, not just matching ones
                # (e.g., if aggregate RSS had 10 bangumi before and now has 8, all 10 are deleted)
                #
                # RECREATION LOGIC WITH DELETION TRACKING:
                # 1. Check if we recently deleted all bangumi for this RSS (within 10 seconds)
                # 2. If NO recent deletion:
                #    - Delete ALL bangumi from this RSS (including all titles, all statuses)
                #    - Record deletion timestamp to prevent subsequent calls from deleting again
                # 3. If YES recent deletion (within 10 seconds):
                #    - Skip deletion (this is part of the same recreation loop)
                # 4. Insert the new bangumi
                #
                # This approach works correctly for recreation loops:
                # - First call: Deletes ALL old bangumi (e.g., 10), records timestamp, inserts first new one
                # - Second call (< 10s): Sees recent deletion, skips delete, just inserts second new one
                # - Third call (< 10s): Sees recent deletion, skips delete, just inserts third new one
                # - Result: Old bangumi (10) replaced with new bangumi (8), no orphans, no accidental deletions
                global _recreation_deletion_tracker

                if data.rss_id:
                    current_time = time.time()
                    last_deletion = _recreation_deletion_tracker.get(data.rss_id)

                    # Clean up old entries (older than 10 seconds)
                    _recreation_deletion_tracker = {
                        rss_id: timestamp
                        for rss_id, timestamp in _recreation_deletion_tracker.items()
                        if current_time - timestamp < _RECREATION_WINDOW_SECONDS
                    }

                    # Check if we need to delete all bangumi for this RSS
                    should_delete_all = (
                        last_deletion is None or
                        (current_time - last_deletion) >= _RECREATION_WINDOW_SECONDS
                    )

                    if should_delete_all:
                        existing_bangumi = engine.bangumi.get_all_by_rss_id(data.rss_id)
                        if existing_bangumi:
                            logger.info(
                                f"[Collector] Recreation: deleting ALL {len(existing_bangumi)} existing bangumi "
                                f"from RSS ID {data.rss_id} (all titles, all statuses) before inserting new ones"
                            )
                            deleted_count = engine.bangumi.delete_all_by_rss_id(data.rss_id)
                            logger.info(
                                f"[Collector] Deleted {deleted_count} bangumi for recreation, "
                                f"now inserting: {data.official_title}"
                            )
                            # Record deletion timestamp to prevent subsequent calls from deleting again
                            _recreation_deletion_tracker[data.rss_id] = current_time
                    else:
                        logger.debug(
                            f"[Collector] Skipping deletion for RSS ID {data.rss_id} - "
                            f"recent deletion detected ({current_time - last_deletion:.1f}s ago), "
                            f"inserting: {data.official_title}"
                        )

                # IMPORTANT: Add Bangumi to database BEFORE downloading torrents
                # so that torrents can be linked to bangumi_id
                engine.bangumi.add(data)

                # Single commit for all delete + insert operations (atomic transaction)
                engine.commit()
                logger.info(
                    f"[Collector] Successfully committed bangumi recreation for {data.official_title} "
                    f"(RSS ID: {data.rss_id})"
                )

                # Now download torrents - they will be linked to the Bangumi
                result = engine.download_bangumi(data)
                return result

            except Exception as e:
                # Rollback all database changes if any operation fails
                engine.rollback()
                logger.error(
                    f"[Collector] Failed to subscribe bangumi {data.official_title}: {e}. "
                    f"All changes rolled back."
                )
                raise


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


def eps_complete():
    """Collect full seasons for bangumi that are not yet complete.

    When eps_complete_from_source is enabled (default), this function will
    use the bangumi's stored RSS link if it's a Mikan season-specific RSS.
    This prevents downloading episodes from other seasons when using
    aggregate RSS feeds like MyBangumi.

    When eps_complete_from_source is disabled, it falls back to keyword
    search which may return episodes from all seasons.
    """
    with RSSEngine() as engine:
        datas = engine.bangumi.not_complete()
        if datas:
            logger.info("Start collecting full season...")
            use_source = settings.bangumi_manage.eps_complete_from_source

            for data in datas:
                if not data.eps_collect:
                    # Extract the first RSS link (rss_link may contain multiple URLs separated by comma)
                    # The first URL is typically the season-specific RSS when eps_complete_from_source is used
                    first_rss_link = (
                        data.rss_link.split(",")[0] if data.rss_link else ""
                    )
                    with SeasonCollector() as collector:
                        # Check if we should use source RSS instead of search
                        if use_source and _is_mikan_season_rss(first_rss_link):
                            # Use the season-specific RSS link directly
                            logger.info(
                                f"[Collector] Using source RSS for {data.official_title}: "
                                f"{first_rss_link}"
                            )
                            collector.collect_season(data, link=first_rss_link)
                        else:
                            # Fall back to keyword search (original behavior)
                            collector.collect_season(data)
                data.eps_collect = True
            engine.bangumi.update_all(datas)
