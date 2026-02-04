"""Tests for Mikan scraper adapter."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from zen_bangumi.effects.adapters.mikan import MikanAdapter, TorrentInfo
from zen_bangumi.domain.parser.mikan_parser import MikanBangumiInfo, SearchResult


class TestTorrentInfo:
    """Tests for TorrentInfo model."""

    def test_torrent_info_creation_with_all_fields(self):
        torrent = TorrentInfo(
            name="[Group] Anime - 01 [1080p].mkv",
            url="magnet:?xt=urn:btih:abc123",
            size="1.5 GB",
            date="2024-01-01",
        )

        assert torrent.name == "[Group] Anime - 01 [1080p].mkv"
        assert torrent.url == "magnet:?xt=urn:btih:abc123"
        assert torrent.size == "1.5 GB"
        assert torrent.date == "2024-01-01"

    def test_torrent_info_creation_with_optional_fields_none(self):
        torrent = TorrentInfo(
            name="Anime Episode",
            url="http://example.com/torrent",
            size=None,
            date=None,
        )

        assert torrent.name == "Anime Episode"
        assert torrent.url == "http://example.com/torrent"
        assert torrent.size is None
        assert torrent.date is None


class TestMikanAdapter:
    """Tests for MikanAdapter class."""

    def test_mikan_adapter_initialization(self):
        adapter = MikanAdapter(timeout=15.0)

        assert adapter.timeout == 15.0
        assert adapter.BASE_URL == "https://mikanani.me"
        assert adapter.SEARCH_URL == "https://mikanani.me/Home/Search"

    def test_mikan_adapter_initialization_with_default_timeout(self):
        adapter = MikanAdapter()

        assert adapter.timeout == 10.0

    async def test_search_returns_async_iterator_with_results(self):
        adapter = MikanAdapter()
        mock_html = """
        <html>
            <body>
                <a href="/Home/Bangumi/123">Test Anime (2024)</a>
            </body>
        </html>
        """

        mock_response = MagicMock()
        mock_response.text = mock_html

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            results = []
            async for result in adapter.search("Test Anime"):
                results.append(result)

            assert len(results) == 1
            assert results[0].mikan_id == "123"
            assert results[0].title == "Test Anime (2024)"

    async def test_search_with_empty_results(self):
        adapter = MikanAdapter()
        mock_html = """
        <html>
            <body>
                <p>No results found</p>
            </body>
        </html>
        """

        mock_response = MagicMock()
        mock_response.text = mock_html

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            results = []
            async for result in adapter.search("NonExistentAnime"):
                results.append(result)

            assert len(results) == 0

    async def test_search_raises_on_http_error(self):
        adapter = MikanAdapter()

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = Exception("Network error")

            with pytest.raises(Exception, match="Network error"):
                async for _ in adapter.search("Test Anime"):
                    pass

    async def test_get_bangumi_info_returns_complete_info(self):
        adapter = MikanAdapter()
        mock_html = """
        <html>
            <body>
                <div class="bangumi-poster" style="url('/images/poster.jpg')"></div>
                <p class="bangumi-title">
                    <a href="/Home/Bangumi/456">Test Bangumi 2024</a>
                </p>
                <a href="/RSS/Bangumi?bangumiId=456&subgroupid=789">Subscribe RSS</a>
            </body>
        </html>
        """

        mock_response = MagicMock()
        mock_response.text = mock_html

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            info = await adapter.get_bangumi_info("456")

            assert info.mikan_id == "456"
            assert info.title == "Test Bangumi 2024"
            assert info.year == "2024"
            assert "bangumiId=456" in info.rss_url
            assert "subgroupid=789" in info.rss_url

    async def test_get_bangumi_info_raises_on_invalid_html(self):
        adapter = MikanAdapter()
        mock_html = """
        <html>
            <body>
                <p>Invalid page</p>
            </body>
        </html>
        """

        mock_response = MagicMock()
        mock_response.text = mock_html

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            with pytest.raises(ValueError, match="Could not extract"):
                await adapter.get_bangumi_info("999")

    async def test_scrape_rss_page_parses_feed_correctly(self):
        adapter = MikanAdapter()
        mock_rss = """
        <?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <item>
                    <title>[Group] Anime - 01 [1080p]</title>
                    <link>magnet:?xt=urn:btih:abc123</link>
                    <enclosure type="application/x-bittorrent" url="magnet:?xt=urn:btih:abc123" />
                    <torrent:contentLength>1610612736</torrent:contentLength>
                    <pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate>
                </item>
            </channel>
        </rss>
        """

        mock_response = MagicMock()
        mock_response.text = mock_rss

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            torrents = await adapter.scrape_rss_page("http://example.com/rss")

            assert len(torrents) >= 1
            assert torrents[0].name == "[Group] Anime - 01 [1080p]"
            assert "abc123" in torrents[0].url

    async def test_scrape_rss_page_handles_empty_feed(self):
        adapter = MikanAdapter()
        mock_rss = """
        <?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title>Empty Feed</title>
            </channel>
        </rss>
        """

        mock_response = MagicMock()
        mock_response.text = mock_rss

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            torrents = await adapter.scrape_rss_page("http://example.com/rss")

            assert len(torrents) == 0

    async def test_scrape_rss_page_raises_on_http_error(self):
        adapter = MikanAdapter()

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = Exception("Network error")

            with pytest.raises(Exception, match="Network error"):
                await adapter.scrape_rss_page("http://example.com/rss")

    def test_format_size_bytes(self):
        adapter = MikanAdapter()
        assert adapter._format_size(500) == "500.0 B"

    def test_format_size_kilobytes(self):
        adapter = MikanAdapter()
        assert adapter._format_size(1024) == "1.0 KB"

    def test_format_size_megabytes(self):
        adapter = MikanAdapter()
        assert adapter._format_size(1048576) == "1.0 MB"

    def test_format_size_gigabytes(self):
        adapter = MikanAdapter()
        assert adapter._format_size(1073741824) == "1.0 GB"

    def test_format_size_terabytes(self):
        adapter = MikanAdapter()
        assert adapter._format_size(1099511627776) == "1.0 TB"

    async def test_search_constructs_correct_url(self):
        adapter = MikanAdapter()
        mock_response = MagicMock()
        mock_response.text = "<html></html>"

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            async for _ in adapter.search("Test Search"):
                pass

            call_args = mock_get.call_args
            assert call_args[0][0] == "https://mikanani.me/Home/Search"
            assert call_args[1]["params"]["searchstr"] == "Test Search"

    async def test_get_bangumi_info_constructs_correct_url(self):
        adapter = MikanAdapter()
        mock_html = """
        <html>
            <body>
                <p class="bangumi-title">
                    <a href="/Home/Bangumi/123">Test</a>
                </p>
                <a href="/RSS/Bangumi?bangumiId=123&subgroupid=456">RSS</a>
            </body>
        </html>
        """

        mock_response = MagicMock()
        mock_response.text = mock_html

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            await adapter.get_bangumi_info("123")

            call_args = mock_get.call_args
            assert call_args[0][0] == "https://mikanani.me/Home/Bangumi/123"
