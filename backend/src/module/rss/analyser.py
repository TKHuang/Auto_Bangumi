import logging
import re

from module.conf import settings
from module.conf.const import MIKAN_SEASON_RSS_PATTERN
from module.models import Bangumi, ResponseModel, RSSItem, Torrent
from module.network import RequestContent
from module.domain.parser.title_parser import TitleParser

logger = logging.getLogger(__name__)


def _is_mikan_season_rss(rss_link: str) -> bool:
    """Check if the RSS link is a Mikan season-specific RSS."""
    if not rss_link:
        return False
    return bool(MIKAN_SEASON_RSS_PATTERN.search(rss_link))


def _needs_season_rss_update(bangumi: Bangumi) -> bool:
    """Check if a bangumi needs its season-specific RSS link updated.

    A bangumi needs update if:
    1. It has no rss_link, OR
    2. Its first rss_link entry is not a valid Mikan season-specific RSS

    Args:
        bangumi: The bangumi to check.

    Returns:
        True if the bangumi needs its season RSS updated.
    """
    if not bangumi.rss_link:
        return True

    # Get the first RSS link (the primary one used by eps_complete_from_source)
    first_rss_link = bangumi.rss_link.split(",")[0]
    return not _is_mikan_season_rss(first_rss_link)


class RSSAnalyser(TitleParser):
    def official_title_parser(
        self,
        bangumi: Bangumi,
        rss: RSSItem,
        torrent: Torrent,
        skip_title_update: bool = False,
    ):
        """Parse official title and metadata from torrent homepage.

        For Mikan parser, also extracts the season-specific RSS link and stores
        it in bangumi.rss_link for use with eps_complete_from_source.

        Args:
            bangumi: Bangumi object to update with parsed metadata.
            rss: RSSItem containing parser configuration.
            torrent: Torrent object with homepage URL.
            skip_title_update: If True, only fetch poster/RSS link but preserve
                existing official_title (used for manual input mode).
        """
        if rss.parser == "mikan":
            try:
                # Use mikan_parser_with_rss to also extract season RSS link
                result = self.mikan_parser_with_rss(torrent.homepage)
                bangumi.poster_link = result.poster_link
                if not skip_title_update:
                    bangumi.official_title = result.official_title

                # Store season-specific RSS link if extracted
                # This enables eps_complete_from_source to use the specific season feed
                if result.season_rss_link:
                    bangumi.rss_link = result.season_rss_link
                    logger.debug(
                        f"[Parser] Extracted season RSS: {result.season_rss_link}"
                    )
            except AttributeError:
                logger.warning("[Parser] Mikan torrent has no homepage info.")
                pass
        elif rss.parser == "tmdb":
            tmdb_title, season, year, poster_link = self.tmdb_parser(
                bangumi.official_title, bangumi.season, settings.rss_parser.language
            )
            if not skip_title_update:
                bangumi.official_title = tmdb_title
                bangumi.season = season
            bangumi.year = year
            bangumi.poster_link = poster_link
        else:
            pass
        if not skip_title_update:
            bangumi.official_title = re.sub(r"[/:.\\]", " ", bangumi.official_title)

    @staticmethod
    def get_rss_torrents(rss_link: str, full_parse: bool = True, apply_filter: bool = True) -> list[Torrent]:
        """Get torrents from RSS feed.
        
        Args:
            rss_link: The RSS URL to fetch torrents from.
            full_parse: If True, fetch all torrents. If False, filter out batch releases.
            apply_filter: If True (default), apply global filter patterns. 
                         If False, fetch all torrents unfiltered (for aggregate RSS pending review).
        """
        with RequestContent() as req:
            if full_parse:
                # For aggregate RSS with pending review, we need unfiltered torrents
                # Pass empty string to bypass global filter
                filter_arg = None if apply_filter else ""
                rss_torrents = req.get_torrents(rss_link, _filter=filter_arg)
            else:
                rss_torrents = req.get_torrents(rss_link, "\\d+-\\d+")
        return rss_torrents

    def torrents_to_data(
        self, torrents: list[Torrent], rss: RSSItem, full_parse: bool = True
    ) -> list:
        new_data = []
        for torrent in torrents:
            bangumi = self.raw_parser(raw=torrent.name)
            if bangumi and bangumi.title_raw not in [i.title_raw for i in new_data]:
                self.official_title_parser(bangumi=bangumi, rss=rss, torrent=torrent)
                # Ensure rss_link is set (fallback to aggregate URL if not set by parser)
                if not bangumi.rss_link:
                    bangumi.rss_link = rss.url
                # Set foreign key to RSS
                bangumi.rss_id = rss.id
                if not full_parse:
                    return [bangumi]
                new_data.append(bangumi)
                logger.info(f"[RSS] New bangumi founded: {bangumi.official_title}")
        return new_data

    def torrent_to_data(
        self,
        torrent: Torrent,
        rss: RSSItem,
        official_title: str | None = None,
        season: int | None = None,
        group_name: str | None = None,
    ) -> Bangumi:
        """Convert a torrent to a Bangumi object.

        Args:
            torrent: Torrent object to parse.
            rss: RSSItem containing parser configuration.
            official_title: Optional manual title override. When provided, skips raw_parser
                   title extraction (avoids BangumiParsingError).
            season: Optional manual season override.
            group_name: Optional manual group name override.

        Returns:
            Bangumi object with parsed or manual data, or None if parsing fails.
        """
        if official_title:
            # Manual override mode: create Bangumi with provided official_title
            # This avoids calling raw_parser which could raise BangumiParsingError
            # title_raw keeps the original torrent name for reference
            bangumi = Bangumi(
                official_title=official_title,
                title_raw=torrent.name,
                season=season if season is not None else 1,
                group_name=group_name if group_name else "Unknown",
                filter=",".join(settings.rss_parser.filter),
            )
        else:
            # Normal mode: use raw_parser to extract data
            bangumi = self.raw_parser(raw=torrent.name)
            if not bangumi:
                return None
            # Apply manual overrides to parsed data if provided
            if season is not None:
                bangumi.season = season
            if group_name:
                bangumi.group_name = group_name

        # Fetch poster and RSS link, but skip title update if manually provided
        self.official_title_parser(
            bangumi=bangumi,
            rss=rss,
            torrent=torrent,
            skip_title_update=bool(official_title),
        )
        # Ensure rss_link is set (fallback to aggregate URL if not set by parser)
        if not bangumi.rss_link:
            bangumi.rss_link = rss.url
        bangumi.rss_id = rss.id
        return bangumi

    def link_to_data(
        self,
        rss: RSSItem,
        official_title: str | None = None,
        season: int | None = None,
        group_name: str | None = None,
    ) -> Bangumi | ResponseModel:
        """Convert an RSS link to a Bangumi object.

        Args:
            rss: RSSItem to parse.
            official_title: Optional manual title override. When provided, skips raw_parser
                   title extraction (avoids BangumiParsingError).
            season: Optional manual season override.
            group_name: Optional manual group name override.

        Returns:
            Bangumi object on success, or ResponseModel with error details.
        """
        torrents = self.get_rss_torrents(rss.url, False)
        if not torrents:
            return ResponseModel(
                status=False,
                status_code=404,
                msg_en="Cannot find any torrent.",
                msg_zh="无法找到种子。",
            )
        for torrent in torrents:
            data = self.torrent_to_data(
                torrent, rss, official_title=official_title, season=season, group_name=group_name
            )
            if data:
                return data
        return ResponseModel(
            status=False,
                status_code=422,
                msg_en="Cannot parse this link.",
                msg_zh="无法解析此链接。",
        )

    def analyse_torrents(self, rss: RSSItem, _filter: str = None, title_raw: str = None) -> list[dict]:
        """Analyse torrents from RSS with optional filtering.
        
        Args:
            rss: RSS item to fetch torrents from
            _filter: Regex pattern to exclude torrents (mark as filtered=True)
            title_raw: If provided, only include torrents that parse to this title_raw
                      (useful for aggregate RSS to show only torrents for a specific bangumi)
        """
        with RequestContent() as req:
            return req.get_torrents_with_filter(rss.url, _filter, title_raw)
