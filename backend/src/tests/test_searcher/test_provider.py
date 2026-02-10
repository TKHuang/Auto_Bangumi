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

    def test_search_url_mikan_site(self, mock_search_config):
        """Test search_url with mikan site returns correct RSSItem."""
        with patch("module.searcher.provider.SEARCH_CONFIG", mock_search_config):
            result = search_url("mikan", ["test", "anime"])
            
            assert isinstance(result, RSSItem)
            assert "test+anime" in result.url
            assert result.aggregate is False
            assert result.parser == "mikan"

    def test_search_url_nyaa_site(self, mock_search_config):
        """Test search_url with nyaa site returns correct RSSItem."""
        with patch("module.searcher.provider.SEARCH_CONFIG", mock_search_config):
            result = search_url("nyaa", ["test", "anime"])
            
            assert isinstance(result, RSSItem)
            assert "test+anime" in result.url
            assert result.aggregate is False
            assert result.parser == "tmdb"

    def test_search_url_dmhy_site(self, mock_search_config):
        """Test search_url with dmhy site returns correct RSSItem."""
        with patch("module.searcher.provider.SEARCH_CONFIG", mock_search_config):
            result = search_url("dmhy", ["test", "anime"])
            
            assert isinstance(result, RSSItem)
            assert "test+anime" in result.url
            assert result.aggregate is False
            assert result.parser == "tmdb"

    def test_search_url_unsupported_site_raises_error(self, mock_search_config):
        """Test search_url with unsupported site raises ValueError."""
        with patch("module.searcher.provider.SEARCH_CONFIG", mock_search_config):
            with pytest.raises(ValueError, match="Site unsupported is not supported"):
                search_url("unsupported", ["test"])

    def test_search_url_keyword_formatting_special_chars(self, mock_search_config):
        """Test search_url converts special characters to plus signs."""
        with patch("module.searcher.provider.SEARCH_CONFIG", mock_search_config):
            result = search_url("mikan", ["test@anime", "season#1"])
            
            # Special chars and spaces should be converted to +
            assert "test+anime+season+1" in result.url

    def test_search_url_keyword_formatting_spaces(self, mock_search_config):
        """Test search_url converts spaces to plus signs."""
        with patch("module.searcher.provider.SEARCH_CONFIG", mock_search_config):
            result = search_url("mikan", ["test anime", "season 1"])
            
            assert "test+anime+season+1" in result.url

    def test_search_url_single_keyword(self, mock_search_config):
        """Test search_url with single keyword."""
        with patch("module.searcher.provider.SEARCH_CONFIG", mock_search_config):
            result = search_url("mikan", ["anime"])
            
            assert "anime" in result.url
            assert result.parser == "mikan"

    def test_search_url_multiple_keywords(self, mock_search_config):
        """Test search_url joins multiple keywords with plus."""
        with patch("module.searcher.provider.SEARCH_CONFIG", mock_search_config):
            result = search_url("mikan", ["test", "anime", "season"])
            
            assert "test+anime+season" in result.url

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
