import logging
from typing import Optional

from module.conf import settings
from module.conf.const import MIKAN_SEASON_RSS_PATTERN
from module.downloader import DownloadClient
from module.models import Bangumi, ResponseModel
from module.rss import RSSEngine
from module.searcher import SearchTorrent

logger = logging.getLogger(__name__)


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
        """Subscribe to a single bangumi.
        
        For non-aggregate RSS, this method handles single bangumi recreation:
        - Deletes existing bangumi from this RSS (typically just 1)
        - Inserts the new bangumi
        - Downloads torrents
        
        For aggregate RSS with multiple bangumi, use subscribe_batch() instead.
        """
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

                # For single bangumi (non-aggregate RSS): Delete existing and insert new
                # This is safe for single bangumi - only affects this one RSS item
                if data.rss_id:
                    existing_bangumi = engine.bangumi.get_all_by_rss_id(data.rss_id)
                    if existing_bangumi:
                        logger.info(
                            f"[Collector] Deleting {len(existing_bangumi)} existing bangumi "
                            f"from RSS ID {data.rss_id} before inserting: {data.official_title}"
                        )
                        engine.bangumi.delete_all_by_rss_id(data.rss_id)

                # Add Bangumi to database
                engine.bangumi.add(data)

                # Commit the transaction
                engine.commit()
                logger.info(
                    f"[Collector] Successfully committed bangumi for {data.official_title} "
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

    @staticmethod
    def subscribe_batch(bangumi_list: list, rss_id: int, parser: str = "mikan"):
        """Subscribe to multiple bangumi in a single atomic transaction.
        
        This method is designed for recreation scenarios where multiple bangumi
        need to be subscribed from a single RSS feed. It:
        1. Deletes all existing bangumi from the RSS ID ONCE
        2. Inserts all new bangumi in a single transaction
        3. Downloads torrents for each bangumi
        
        Args:
            bangumi_list: List of Bangumi objects to subscribe
            rss_id: The RSS ID these bangumi belong to
            parser: Parser type (default: "mikan")
            
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
        
        with RSSEngine() as engine:
            try:
                # Step 1: Delete ALL existing bangumi from this RSS (ONCE)
                existing_bangumi = engine.bangumi.get_all_by_rss_id(rss_id)
                if existing_bangumi:
                    logger.info(
                        f"[Collector] Batch recreation: deleting ALL {len(existing_bangumi)} existing bangumi "
                        f"from RSS ID {rss_id} before inserting {len(bangumi_list)} new ones"
                    )
                    deleted_count = engine.bangumi.delete_all_by_rss_id(rss_id)
                    logger.info(f"[Collector] Deleted {deleted_count} bangumi for batch recreation")
                
                # Step 2: Insert all new bangumi
                success_count = 0
                failed_titles = []
                
                for data in bangumi_list:
                    try:
                        data.added = True
                        data.eps_collect = True
                        data.rss_id = rss_id
                        
                        # Add bangumi to database
                        engine.bangumi.add(data)
                        success_count += 1
                        logger.debug(f"[Collector] Batch insert: {data.official_title}")
                    except Exception as e:
                        logger.error(f"[Collector] Failed to insert {data.official_title}: {e}")
                        failed_titles.append(data.official_title)
                
                # Commit all inserts in single transaction
                engine.commit()
                logger.info(
                    f"[Collector] Batch recreation committed: {success_count}/{len(bangumi_list)} bangumi "
                    f"for RSS ID {rss_id}"
                )
                
                # Step 3: Download torrents for each bangumi (after commit so IDs are assigned)
                download_results = []
                for data in bangumi_list:
                    if data.official_title not in failed_titles:
                        try:
                            result = engine.download_bangumi(data)
                            download_results.append((data.official_title, result))
                        except Exception as e:
                            logger.error(f"[Collector] Failed to download torrents for {data.official_title}: {e}")
                
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
                engine.rollback()
                logger.error(f"[Collector] Batch subscription failed: {e}. All changes rolled back.")
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
