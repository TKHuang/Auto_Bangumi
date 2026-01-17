import logging
import re

from module.conf import settings
from module.downloader import DownloadClient
from module.models import Bangumi, ResponseModel
from module.rss import RSSEngine
from module.searcher import SearchTorrent

logger = logging.getLogger(__name__)

# Pattern to match Mikan season-specific RSS links
MIKAN_SEASON_RSS_PATTERN = re.compile(
    r"mikanani\.me/RSS/Bangumi\?.*bangumiId=\d+.*subgroupid=\d+"
)


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
            if self.add_torrent(torrents, bangumi):
                logger.info(
                    f"Collections of {bangumi.official_title} Season {bangumi.season} completed."
                )
                for torrent in torrents:
                    torrent.downloaded = True
                bangumi.eps_collect = True
                if engine.bangumi.update(bangumi):
                    engine.bangumi.add(bangumi)
                engine.torrent.add_all(torrents)
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
            engine.add_rss(
                rss_link=data.rss_link,
                name=data.official_title,
                aggregate=False,
                parser=parser,
            )
            result = engine.download_bangumi(data)
            engine.bangumi.add(data)
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
                    first_rss_link = data.rss_link.split(",")[0] if data.rss_link else ""
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
