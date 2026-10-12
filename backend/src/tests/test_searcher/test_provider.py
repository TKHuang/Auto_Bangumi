"""Unit tests for module.searcher.provider.search_url function."""

import pytest
from unittest.mock import patch

from module.searcher.provider import search_url
from module.models import RSSItem


class TestSearchUrl:
    """Test cases for search_url function."""

    @pytest.fixture
    def mock_search_config(self):
        """Mock SEARCH_CONFIG with known test values."""
        return {
            "mikan": "https://mikanani.me/RSS/Search?searchstr=%s",
            "nyaa": "https://nyaa.si/?page=rss&q=%s&c=0_0&f=0",
            "dmhy": "http://dmhy.org/topics/rss/rss.xml?keyword=%s",
        }

    @pytest.mark.parametrize(
        "site, expected_parser",
        [("mikan", "mikan"), ("nyaa", "tmdb"), ("dmhy", "tmdb")],
    )
    def test_search_url_site(self, mock_search_config, site, expected_parser):
        """Test search_url with each supported site returns correct RSSItem."""
        with patch("module.searcher.provider.SEARCH_CONFIG", mock_search_config):
            result = search_url(site, ["test", "anime"])

            assert isinstance(result, RSSItem)
            assert "test+anime" in result.url
            assert result.aggregate is False
            assert result.parser == expected_parser

    def test_search_url_unsupported_site_raises_error(self, mock_search_config):
        """Test search_url with unsupported site raises ValueError."""
        with patch("module.searcher.provider.SEARCH_CONFIG", mock_search_config):
            with pytest.raises(ValueError, match="Site unsupported is not supported"):
                search_url("unsupported", ["test"])

    @pytest.mark.parametrize(
        "keywords",
        [["test@anime", "season#1"], ["test anime", "season 1"]],
        ids=["special_chars", "spaces"],
    )
    def test_search_url_keyword_formatting(self, mock_search_config, keywords):
        """Test search_url converts special characters and spaces to plus signs."""
        with patch("module.searcher.provider.SEARCH_CONFIG", mock_search_config):
            result = search_url("mikan", keywords)

            assert "test+anime+season+1" in result.url

    @pytest.mark.parametrize(
        "keywords, expected_substring",
        [(["anime"], "anime"), (["test", "anime", "season"], "test+anime+season")],
        ids=["single_keyword", "multiple_keywords"],
    )
    def test_search_url_keyword_count(self, mock_search_config, keywords, expected_substring):
        """Test search_url with a single keyword and with several joined by plus."""
        with patch("module.searcher.provider.SEARCH_CONFIG", mock_search_config):
            result = search_url("mikan", keywords)

            assert expected_substring in result.url
            assert result.parser == "mikan"

    def test_search_url_rss_item_fields(self, mock_search_config):
        """Test search_url RSSItem has all required fields."""
        with patch("module.searcher.provider.SEARCH_CONFIG", mock_search_config):
            result = search_url("nyaa", ["test"])
            
            assert hasattr(result, "url")
            assert hasattr(result, "aggregate")
            assert hasattr(result, "parser")
            assert result.url.startswith("https://")
            assert result.aggregate is False
            assert result.parser in ["mikan", "tmdb"]
