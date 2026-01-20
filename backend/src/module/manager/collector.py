import logging

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

            # Use hash-based deduplication to prevent duplicate torrents
            new_torrents = engine.torrent.check_new_by_hash(torrents)
            if not new_torrents:
                logger.info(
                    f"No new torrents for {bangumi.official_title} (all duplicates filtered)."
                )
                return ResponseModel(
                    status=False,
                    status_code=406,
                    msg_en=f"No new episodes found for {bangumi.official_title}.",
                    msg_zh=f"{bangumi.official_title} 没有找到新剧集。",
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
                engine.torrent.add_all(new_torrents)
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
            data.added = True
            data.eps_collect = True

            # Check if bangumi with same composite key exists BEFORE adding RSS
            # This prevents orphan RSS entries when duplicate is detected
            group_name = data.group_name if data.group_name else "Unknown"
            existing = engine.bangumi.search_by_composite_key(
                title_raw=data.title_raw,
                season=data.season,
                group_name=group_name,
            )

            if existing:
                # Check if it's from a different RSS source by comparing URLs
                existing_rss = engine.rss.search_id(existing.rss_id) if existing.rss_id else None
                existing_rss_url = existing_rss.url if existing_rss else None

                if existing_rss_url and existing_rss_url != data.rss_link:
                    # Different RSS source - this is a conflict (duplicate subscription)
                    logger.warning(
                        f"[Collector] Bangumi already subscribed from different RSS: "
                        f"title_raw='{data.title_raw}', season={data.season}, group='{group_name}' "
                        f"(existing RSS URL: {existing_rss_url}, new RSS URL: {data.rss_link})"
                    )
                    raise ValueError(
                        f"Bangumi '{data.official_title}' (group: {group_name}) is already subscribed "
                        f"from another RSS source. Delete the existing subscription first."
                    )
                else:
                    # Same RSS source - allow recreation with updated settings
                    logger.debug(
                        f"[Collector] Deleting existing Bangumi rule for recreation: "
                        f"{existing.official_title} (ID: {existing.id})"
                    )
                    # Reuse existing RSS ID if available
                    if existing.rss_id:
                        data.rss_id = existing.rss_id
                    engine.bangumi.delete_one(existing.id)
                    engine.commit()

            # Only create RSS if not already set (for aggregate RSS recreation or reuse)
            if not data.rss_id:
                # Add the RSS feed
                engine.add_rss(
                    rss_link=data.rss_link,
                    name=data.official_title,
                    aggregate=False,
                    parser=parser,
                )

                # Get the RSS ID by searching for the RSS item with matching URL
                all_rss = engine.rss.search_all()
                for rss_item in all_rss:
                    if rss_item.url == data.rss_link:
                        data.rss_id = rss_item.id
                        break

            # IMPORTANT: Add Bangumi to database BEFORE downloading torrents
            # so that torrents can be linked to bangumi_id
            engine.bangumi.add(data)
            engine.commit()  # Ensure Bangumi is committed and has an ID

            # Now download torrents - they will be linked to the Bangumi
            result = engine.download_bangumi(data)
            return result


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
