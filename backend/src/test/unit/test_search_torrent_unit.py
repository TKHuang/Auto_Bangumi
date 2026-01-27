"""Unit tests for SearchTorrent.

This module contains unit tests for the SearchTorrent class methods.
"""

from unittest.mock import MagicMock, patch

import pytest

from module.models import Bangumi, RSSItem, Torrent
from module.searcher.searcher import SearchTorrent


class TestSearchTorrentAnalyseKeyword:
    """Tests for SearchTorrent.analyse_keyword method."""

    @pytest.mark.unit
    def test_analyse_keyword_yields_parsed_results(self):
        """Test that analyse_keyword yields JSON-encoded bangumi results."""
        # Create mock torrents
        mock_torrents = [
            Torrent(
                name="[TestGroup] My Anime - 01 [1080p].mkv",
                url="https://example.com/torrent1.torrent",
                homepage="https://mikanani.me/Home/Episode/12345",
            ),
            Torrent(
                name="[TestGroup] My Anime - 02 [1080p].mkv",
                url="https://example.com/torrent2.torrent",
                homepage="https://mikanani.me/Home/Episode/12346",
            ),
        ]

        # Create a mock RSSItem for the search result
        mock_rss_item = RSSItem(
            url="https://mikanani.me/RSS/Search?searchstr=MyAnime",
            aggregate=False,
            parser="mikan",
        )

        # Create mock bangumi to be returned by torrent_to_data
        mock_bangumi = Bangumi(
            official_title="My Anime",
            title_raw="[TestGroup] My Anime",
            season=1,
            group_name="TestGroup",
        )

        with (
            patch(
                "module.searcher.searcher.search_url",
                return_value=mock_rss_item,
            ),
            patch.object(
                SearchTorrent,
                "get_torrents",
                return_value=mock_torrents,
            ),
            patch.object(
                SearchTorrent,
                "torrent_to_data",
                return_value=mock_bangumi,
            ),
            patch.object(
                SearchTorrent,
                "special_url",
                return_value=RSSItem(
                    url="https://mikanani.me/RSS/Bangumi?bangumiId=12345",
                    aggregate=False,
                    parser="mikan",
                ),
            ),
        ):
            searcher = SearchTorrent()
            results = list(searcher.analyse_keyword(["MyAnime"], site="mikan", limit=5))

        # Should yield at least one JSON result
        assert len(results) >= 1
        # Each result should be a valid JSON string
        import json

        for result in results:
            parsed = json.loads(result)
            assert "official_title" in parsed
            assert parsed["official_title"] == "My Anime"

    @pytest.mark.unit
    def test_analyse_keyword_respects_limit(self):
        """Test that analyse_keyword respects the limit parameter."""
        # Create 10 torrents, each with different URLs to create unique results
        mock_torrents = [
            Torrent(
                name=f"[TestGroup] Anime {i} - 01 [1080p].mkv",
                url=f"https://example.com/torrent{i}.torrent",
                homepage=f"https://mikanani.me/Home/Episode/{10000 + i}",
            )
            for i in range(10)
        ]

        mock_rss_item = RSSItem(
            url="https://mikanani.me/RSS/Search?searchstr=Anime",
            aggregate=False,
            parser="mikan",
        )

        # Return different bangumi for each torrent
        def create_bangumi(torrent, rss, **kwargs):
            idx = mock_torrents.index(torrent)
            return Bangumi(
                official_title=f"Anime {idx}",
                title_raw=f"[TestGroup] Anime {idx}",
                season=1,
                group_name="TestGroup",
            )

        # Return different URLs for special_url
        call_count = [0]

        def mock_special_url(data, site):
            result = RSSItem(
                url=f"https://mikanani.me/RSS/Bangumi?bangumiId={call_count[0]}",
                aggregate=False,
                parser="mikan",
            )
            call_count[0] += 1
            return result

        with (
            patch(
                "module.searcher.searcher.search_url",
                return_value=mock_rss_item,
            ),
            patch.object(
                SearchTorrent,
                "get_torrents",
                return_value=mock_torrents,
            ),
            patch.object(
                SearchTorrent,
                "torrent_to_data",
                side_effect=create_bangumi,
            ),
            patch.object(
                SearchTorrent,
                "special_url",
                side_effect=mock_special_url,
            ),
        ):
            searcher = SearchTorrent()

            # Request limit of 3
            results = list(searcher.analyse_keyword(["Anime"], site="mikan", limit=3))

        # Should yield exactly 3 results (the limit)
        assert len(results) == 3

    @pytest.mark.unit
    def test_analyse_keyword_empty_returns_nothing(self):
        """Test that analyse_keyword returns nothing when no torrents found."""
        mock_rss_item = RSSItem(
            url="https://mikanani.me/RSS/Search?searchstr=NonExistent",
            aggregate=False,
            parser="mikan",
        )

        with (
            patch(
                "module.searcher.searcher.search_url",
                return_value=mock_rss_item,
            ),
            patch.object(
                SearchTorrent,
                "get_torrents",
                return_value=[],  # No torrents found
            ),
        ):
            searcher = SearchTorrent()
            results = list(searcher.analyse_keyword(["NonExistent"], site="mikan"))

        # Should return empty list
        assert len(results) == 0


class TestSearchTorrentSearchSeason:
    """Tests for SearchTorrent.search_season method."""

    @pytest.mark.unit
    def test_search_season_filters_by_title_raw(self):
        """Test that search_season filters torrents by title_raw correctly."""
        # Create mixed torrents - some matching, some not
        mock_torrents = [
            Torrent(
                name="[TestGroup] My Anime - 01 [1080p].mkv",
                url="https://example.com/torrent1.torrent",
            ),
            Torrent(
                name="[TestGroup] My Anime - 02 [1080p].mkv",
                url="https://example.com/torrent2.torrent",
            ),
            Torrent(
                name="[OtherGroup] Different Anime - 01 [720p].mkv",
                url="https://example.com/torrent3.torrent",
            ),
            Torrent(
                name="[TestGroup] Another Show - 01 [1080p].mkv",
                url="https://example.com/torrent4.torrent",
            ),
        ]

        mock_rss_item = RSSItem(
            url="https://mikanani.me/RSS/Bangumi?bangumiId=12345",
            aggregate=False,
            parser="mikan",
        )

        # Bangumi to search for - should match only torrents containing "My Anime"
        bangumi = Bangumi(
            official_title="My Anime",
            title_raw="My Anime",  # This is what we search for in torrent.name
            season=1,
            group_name="TestGroup",
        )

        with (
            patch.object(
                SearchTorrent,
                "special_url",
                return_value=mock_rss_item,
            ),
            patch.object(
                SearchTorrent,
                "search_torrents",
                return_value=mock_torrents,
            ),
        ):
            searcher = SearchTorrent()
            results = searcher.search_season(bangumi, site="mikan")

        # Should only return torrents containing "My Anime" in their name
        assert len(results) == 2
        for torrent in results:
            assert "My Anime" in torrent.name
