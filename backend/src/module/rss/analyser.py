import logging
import re

from module.conf import settings
from module.conf.const import MIKAN_SEASON_RSS_PATTERN
from module.models import Bangumi, ResponseModel, RSSItem, Torrent
from module.network import RequestContent
from module.parser import TitleParser

from .engine import RSSEngine

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
    def official_title_parser(self, bangumi: Bangumi, rss: RSSItem, torrent: Torrent):
        """Parse official title and metadata from torrent homepage.

        For Mikan parser, also extracts the season-specific RSS link and stores
        it in bangumi.rss_link for use with eps_complete_from_source.

        Args:
            bangumi: Bangumi object to update with parsed metadata.
            rss: RSSItem containing parser configuration.
            torrent: Torrent object with homepage URL.
        """
        if rss.parser == "mikan":
            try:
                # Use mikan_parser_with_rss to also extract season RSS link
                result = self.mikan_parser_with_rss(torrent.homepage)
                bangumi.poster_link = result.poster_link
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
            bangumi.official_title = tmdb_title
            bangumi.year = year
            bangumi.season = season
            bangumi.poster_link = poster_link
        else:
            pass
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
        title: str | None = None,
        season: int | None = None,
        group_name: str | None = None,
    ) -> Bangumi:
        """Convert a torrent to a Bangumi object.

        Args:
            torrent: Torrent object to parse.
            rss: RSSItem containing parser configuration.
            title: Optional manual title override. When provided, skips raw_parser
                   title extraction (avoids BangumiParsingError).
            season: Optional manual season override.
            group_name: Optional manual group name override.

        Returns:
            Bangumi object with parsed or manual data, or None if parsing fails.
        """
        if title:
            # Manual override mode: create Bangumi with provided title
            # This avoids calling raw_parser which could raise BangumiParsingError
            bangumi = Bangumi(
                official_title=title,
                title_raw=title,
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

        self.official_title_parser(bangumi=bangumi, rss=rss, torrent=torrent)
        # Ensure rss_link is set (fallback to aggregate URL if not set by parser)
        if not bangumi.rss_link:
            bangumi.rss_link = rss.url
        bangumi.rss_id = rss.id
        return bangumi

    def rss_to_data(
        self, rss: RSSItem, engine: RSSEngine, full_parse: bool = True
    ) -> list[Bangumi]:
        # For aggregate RSS, get unfiltered torrents so we can create pending review records
        # For non-aggregate RSS, apply global filter as before
        apply_filter = not rss.aggregate
        rss_torrents = self.get_rss_torrents(rss.url, full_parse, apply_filter=apply_filter)
        
        torrents_to_add, matched_pairs = engine.bangumi.match_list(
            rss_torrents, rss.url
        )

        # For aggregate RSS with Mikan parser, update existing bangumi's season-specific RSS
        # This enables eps_complete_from_source to work for bangumi matched from aggregate feeds
        if rss.parser == "mikan" and matched_pairs:
            self._update_matched_bangumi_rss(matched_pairs, rss, engine)

        if not torrents_to_add:
            logger.debug("[RSS] No new title has been found.")
            return []

        # For aggregate RSS, check global filter and create pending review records
        if rss.aggregate:
            active_bangumi = []
            pending_bangumi = []
            global_filter_patterns = settings.rss_parser.filter

            # Process each torrent individually to preserve original torrent name for filter matching
            for torrent in torrents_to_add:
                bangumi = self.raw_parser(raw=torrent.name)
                if not bangumi:
                    continue
                    
                # Skip duplicates within this batch (same title_raw)
                if bangumi.title_raw in [b.title_raw for b in active_bangumi + pending_bangumi]:
                    continue
                
                self.official_title_parser(bangumi=bangumi, rss=rss, torrent=torrent)
                # Ensure rss_link is set (fallback to aggregate URL if not set by parser)
                if not bangumi.rss_link:
                    bangumi.rss_link = rss.url
                # Set foreign key to RSS
                bangumi.rss_id = rss.id
                
                # Check if bangumi already exists (active or pending) by composite key
                if engine.bangumi.exists_by_composite_key(
                    bangumi.official_title, bangumi.season, bangumi.group_name
                ):
                    logger.debug(
                        f"[RSS] Skipping duplicate bangumi: {bangumi.official_title} "
                        f"(season={bangumi.season}, group={bangumi.group_name})"
                    )
                    continue

                # Check if ORIGINAL TORRENT NAME matches any global filter pattern
                # This is the key fix - use torrent.name, not bangumi.title_raw
                matched_patterns = []
                for pattern in global_filter_patterns:
                    if re.search(pattern, torrent.name, re.IGNORECASE):
                        matched_patterns.append(pattern)

                if matched_patterns:
                    # Torrent matches global filter - save as pending review
                    bangumi.pending_review = True
                    bangumi.global_filter_matches = ",".join(matched_patterns)
                    pending_bangumi.append(bangumi)
                    logger.info(
                        f"[RSS] Pending review bangumi: {bangumi.official_title} "
                        f"(filtered by: {bangumi.global_filter_matches})"
                    )
                else:
                    # Torrent passes global filter - save as active
                    active_bangumi.append(bangumi)
                    logger.info(f"[RSS] New bangumi founded: {bangumi.official_title}")
                
                if not full_parse:
                    # For quick parse, return first bangumi found
                    if active_bangumi:
                        engine.bangumi.add_all(active_bangumi)
                        return active_bangumi
                    elif pending_bangumi:
                        engine.bangumi.add_all(pending_bangumi)
                        return []  # Don't return pending for immediate download

            # Add all bangumi (active and pending) to database
            all_bangumi = active_bangumi + pending_bangumi
            if all_bangumi:
                engine.bangumi.add_all(all_bangumi)
            return active_bangumi  # Only return active bangumi for immediate download
        else:
            # Non-aggregate RSS - original behavior (no global filter check)
            new_data = self.torrents_to_data(torrents_to_add, rss, full_parse)
            if not new_data:
                return []
            engine.bangumi.add_all(new_data)
            return new_data

    def _update_matched_bangumi_rss(
        self,
        matched_pairs: list[tuple[Bangumi, Torrent]],
        rss: RSSItem,
        engine: RSSEngine,
    ):
        """Update matched bangumi with season-specific RSS links.

        For aggregate RSS feeds, existing bangumi may not have a season-specific
        RSS link. This method extracts the season RSS from the torrent's homepage
        and updates the bangumi's rss_link field.

        Args:
            matched_pairs: List of (bangumi, torrent) tuples from match_list.
            rss: The RSS item being processed.
            engine: RSSEngine for database updates.
        """
        # Track which bangumi we've already processed (by title_raw)
        processed = set()

        for bangumi, torrent in matched_pairs:
            # Skip if we've already processed this bangumi
            if bangumi.title_raw in processed:
                continue
            processed.add(bangumi.title_raw)

            # Skip if bangumi already has a valid season-specific RSS
            if not _needs_season_rss_update(bangumi):
                continue

            # Skip if torrent has no homepage
            if not torrent.homepage:
                continue

            try:
                # Extract season-specific RSS from torrent homepage
                result = self.mikan_parser_with_rss(torrent.homepage)
                if result.season_rss_link:
                    # Prepend season-specific RSS to the beginning of rss_link
                    # This ensures eps_complete_from_source uses the season RSS
                    if bangumi.rss_link:
                        new_rss_link = f"{result.season_rss_link},{bangumi.rss_link}"
                    else:
                        new_rss_link = result.season_rss_link

                    engine.bangumi.update_rss(bangumi.title_raw, new_rss_link)
                    logger.info(
                        f"[RSS] Updated {bangumi.official_title} with season RSS: "
                        f"{result.season_rss_link}"
                    )
            except Exception as e:
                logger.warning(
                    f"[RSS] Failed to extract season RSS for {bangumi.official_title}: {e}"
                )

    def link_to_data(
        self,
        rss: RSSItem,
        title: str | None = None,
        season: int | None = None,
        group_name: str | None = None,
    ) -> Bangumi | ResponseModel:
        """Convert an RSS link to a Bangumi object.

        Args:
            rss: RSSItem to parse.
            title: Optional manual title override. When provided, skips raw_parser
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
                status_code=406,
                msg_en="Cannot find any torrent.",
                msg_zh="无法找到种子。",
            )
        for torrent in torrents:
            data = self.torrent_to_data(
                torrent, rss, title=title, season=season, group_name=group_name
            )
            if data:
                return data
        return ResponseModel(
            status=False,
            status_code=406,
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
