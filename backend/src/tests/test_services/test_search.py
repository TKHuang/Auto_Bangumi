"""TDD tests for search service.

Tests use mocked network and parser components to verify search behavior.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from module.services.search import get_providers, search


class TestGetProviders:
    """Test get_providers function."""

    def test_returns_provider_list(self):
        """get_providers returns list of provider names."""
        providers = get_providers()
        assert isinstance(providers, list)
        assert len(providers) > 0
        assert "mikan" in providers

    def test_returns_all_configured_providers(self):
        """get_providers returns all providers from SEARCH_CONFIG."""
        with patch("module.services.search.SEARCH_CONFIG", {"mikan": "url1", "nyaa": "url2"}):
            providers = get_providers()
            assert providers == ["mikan", "nyaa"]


class TestSearch:
    """Test search async generator."""

    @pytest.fixture
    def mock_request_content(self):
        """Create mocked RequestContent."""
        mock_req = MagicMock()
        mock_req.__enter__ = MagicMock(return_value=mock_req)
        mock_req.__exit__ = MagicMock(return_value=False)
        return mock_req

    @pytest.fixture
    def mock_parser(self):
        """Create mocked RSSAnalyser."""
        return MagicMock()

    @pytest.fixture
    def sample_torrent(self):
        """Create sample torrent."""
        torrent = MagicMock()
        torrent.name = "[SubGroup] Test Bangumi - 01 [1080p].mkv"
        torrent.url = "magnet:?xt=urn:btih:abc123"
        torrent.homepage = "https://example.com/bangumi/123"
        return torrent

    @pytest.fixture
    def sample_bangumi(self):
        """Create sample bangumi."""
        bangumi = MagicMock()
        bangumi.official_title = "Test Bangumi"
        bangumi.title_raw = "Test Bangumi"
        bangumi.season = 1
        bangumi.group_name = "SubGroup"
        bangumi.poster_link = "https://example.com/poster.jpg"
        bangumi.rss_link = "https://example.com/rss/123"
        def _mock_dump(**kwargs):
            return {
                "official_title": "Test Bangumi",
                "title_raw": "Test Bangumi",
                "season": 1,
                "group_name": "SubGroup",
                "poster_link": "https://example.com/poster.jpg",
                "rss_link": bangumi.rss_link,
            }
        bangumi.dict.side_effect = _mock_dump
        bangumi.model_dump.side_effect = _mock_dump
        return bangumi

    @pytest.fixture
    def sample_rss_item(self):
        """Create sample RSS item."""
        rss = MagicMock()
        rss.url = "https://example.com/rss"
        rss.aggregate = False
        rss.parser = "mikan"
        return rss

    @pytest.mark.asyncio
    async def test_search_yields_bangumi_json(
        self, mock_request_content, mock_parser, sample_torrent, sample_bangumi, sample_rss_item
    ):
        """search yields JSON-encoded Bangumi objects."""
        mock_request_content.get_torrents.return_value = [sample_torrent]
        mock_parser.raw_parser.return_value = sample_bangumi
        mock_parser.torrent_to_data.return_value = sample_bangumi

        with patch("module.services.search.RequestContent", return_value=mock_request_content):
            with patch("module.services.search.RSSAnalyser", return_value=mock_parser):
                with patch("module.services.search.search_url") as mock_search_url:
                    mock_search_url.return_value = sample_rss_item

                    results = []
                    async for result in search(["test"], provider="mikan"):
                        results.append(result)

                    assert len(results) == 1
                    # Verify it's valid JSON
                    parsed = json.loads(results[0])
                    assert parsed["official_title"] == "Test Bangumi"
                    assert parsed["season"] == 1

    @pytest.mark.asyncio
    async def test_search_respects_limit(
        self, mock_request_content, mock_parser, sample_torrent, sample_rss_item
    ):
        """search respects limit parameter."""
        # Create 10 unique torrents
        torrents = [MagicMock(name=f"torrent_{i}") for i in range(10)]
        for torrent in torrents:
            torrent.name = f"[SubGroup] Test Bangumi {id(torrent)} - 01 [1080p].mkv"
        mock_request_content.get_torrents.return_value = torrents

        # Create unique bangumi for each torrent
        def create_bangumi(torrent, rss):
            b = MagicMock()
            b.official_title = f"Test Bangumi {id(torrent)}"
            b.title_raw = f"Test Bangumi {id(torrent)}"
            b.season = 1
            b.group_name = "SubGroup"
            b.rss_link = f"https://example.com/rss/{id(torrent)}"
            dump = {
                "official_title": b.official_title,
                "title_raw": b.title_raw,
                "season": 1,
                "group_name": "SubGroup",
                "rss_link": b.rss_link,
            }
            b.dict.return_value = dump
            b.model_dump.return_value = dump
            return b

        mock_parser.raw_parser.side_effect = lambda raw: create_bangumi(raw, None)
        mock_parser.torrent_to_data.side_effect = create_bangumi

        with patch("module.services.search.RequestContent", return_value=mock_request_content):
            with patch("module.services.search.RSSAnalyser", return_value=mock_parser):
                with patch("module.services.search.search_url") as mock_search_url:
                    # Return different URLs based on keywords to avoid deduplication
                    def search_url_side_effect(provider, keywords):
                        rss = MagicMock()
                        # Use keywords to generate unique URL
                        keyword_str = "_".join(str(k) for k in keywords) if keywords else "default"
                        rss.url = f"https://example.com/rss/{keyword_str}"
                        return rss
                    mock_search_url.side_effect = search_url_side_effect

                    results = []
                    async for result in search(["test"], provider="mikan", limit=3):
                        results.append(result)

                    assert len(results) == 3

    @pytest.mark.asyncio
    async def test_search_skips_duplicates(
        self, mock_request_content, mock_parser, sample_torrent, sample_rss_item
    ):
        """search skips duplicate RSS links."""
        # Create 3 torrents
        torrents = [sample_torrent for _ in range(3)]
        mock_request_content.get_torrents.return_value = torrents

        # All bangumi have same RSS link (duplicates)
        same_bangumi = MagicMock()
        same_bangumi.official_title = "Test Bangumi"
        same_bangumi.title_raw = "Test Bangumi"
        same_bangumi.season = 1
        same_bangumi.group_name = "SubGroup"
        same_bangumi.rss_link = "https://example.com/rss/same"
        _same_dump = {
            "official_title": "Test Bangumi",
            "title_raw": "Test Bangumi",
            "season": 1,
            "group_name": "SubGroup",
            "rss_link": "https://example.com/rss/same",
        }
        same_bangumi.dict.return_value = _same_dump
        same_bangumi.model_dump.return_value = _same_dump

        mock_parser.raw_parser.return_value = same_bangumi
        mock_parser.torrent_to_data.return_value = same_bangumi

        with patch("module.services.search.RequestContent", return_value=mock_request_content):
            with patch("module.services.search.RSSAnalyser", return_value=mock_parser):
                with patch("module.services.search.search_url") as mock_search_url:
                    mock_search_url.return_value = sample_rss_item
                    with patch("module.services.search._build_special_url") as mock_special:
                        special_rss = MagicMock()
                        special_rss.url = "https://example.com/rss/same"
                        mock_special.return_value = special_rss

                        results = []
                        async for result in search(["test"], provider="mikan"):
                            results.append(result)

                        # Only 1 result despite 3 torrents (duplicates filtered)
                        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_search_skips_unparseable_torrents(
        self, mock_request_content, mock_parser, sample_torrent, sample_rss_item
    ):
        """search skips torrents that cannot be parsed."""
        mock_request_content.get_torrents.return_value = [sample_torrent]
        # raw_parser returns None (unparseable)
        mock_parser.raw_parser.return_value = None

        with patch("module.services.search.RequestContent", return_value=mock_request_content):
            with patch("module.services.search.RSSAnalyser", return_value=mock_parser):
                with patch("module.services.search.search_url") as mock_search_url:
                    mock_search_url.return_value = sample_rss_item

                    results = []
                    async for result in search(["test"], provider="mikan"):
                        results.append(result)

                    assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_invalid_provider_raises_error(self):
        """search raises ValueError for invalid provider."""
        with pytest.raises(ValueError, match="Provider 'invalid' is not supported"):
            async for _ in search(["test"], provider="invalid"):
                pass

    @pytest.mark.asyncio
    async def test_search_calls_search_url_with_keywords(
        self, mock_request_content, mock_parser, sample_rss_item
    ):
        """search calls search_url with correct keywords."""
        mock_request_content.get_torrents.return_value = []

        with patch("module.services.search.RequestContent", return_value=mock_request_content):
            with patch("module.services.search.RSSAnalyser", return_value=mock_parser):
                with patch("module.services.search.search_url") as mock_search_url:
                    mock_search_url.return_value = sample_rss_item

                    async for _ in search(["keyword1", "keyword2"], provider="nyaa"):
                        pass

                    mock_search_url.assert_called_once_with("nyaa", ["keyword1", "keyword2"])

    @pytest.mark.asyncio
    async def test_search_sets_rss_link_on_bangumi(
        self, mock_request_content, mock_parser, sample_torrent, sample_bangumi, sample_rss_item
    ):
        """search sets rss_link on returned bangumi."""
        mock_request_content.get_torrents.return_value = [sample_torrent]
        mock_parser.raw_parser.return_value = sample_bangumi
        mock_parser.torrent_to_data.return_value = sample_bangumi

        with patch("module.services.search.RequestContent", return_value=mock_request_content):
            with patch("module.services.search.RSSAnalyser", return_value=mock_parser):
                with patch("module.services.search.search_url") as mock_search_url:
                    mock_search_url.return_value = sample_rss_item
                    with patch("module.services.search._build_special_url") as mock_special:
                        special_rss = MagicMock()
                        special_rss.url = "https://example.com/rss/special"
                        mock_special.return_value = special_rss

                        results = []
                        async for result in search(["test"], provider="mikan"):
                            results.append(result)

                        parsed = json.loads(results[0])
                        assert parsed["rss_link"] == "https://example.com/rss/special"


class TestBuildSpecialUrl:
    """Test _build_special_url helper function."""

    def test_builds_url_from_bangumi_metadata(self):
        """_build_special_url builds URL from bangumi group_name and official_title."""
        from module.services.search import _build_special_url

        bangumi = MagicMock()
        bangumi.official_title = "Test Bangumi"
        bangumi.group_name = "SubGroup"

        with patch("module.services.search.search_url") as mock_search_url:
            special_rss = MagicMock()
            special_rss.url = "https://example.com/rss/special"
            mock_search_url.return_value = special_rss

            result = _build_special_url(bangumi, "mikan")

            # Should call search_url with group_name and official_title
            mock_search_url.assert_called_once_with("mikan", ["SubGroup", "Test Bangumi"])
            assert result.url == "https://example.com/rss/special"

    def test_skips_none_attributes(self):
        """_build_special_url skips None attributes."""
        from module.services.search import _build_special_url

        bangumi = MagicMock()
        bangumi.official_title = "Test Bangumi"
        bangumi.group_name = None  # None should be skipped

        with patch("module.services.search.search_url") as mock_search_url:
            special_rss = MagicMock()
            special_rss.url = "https://example.com/rss/special"
            mock_search_url.return_value = special_rss

            _build_special_url(bangumi, "mikan")

            # Should only include official_title (group_name is None)
            mock_search_url.assert_called_once_with("mikan", ["Test Bangumi"])
