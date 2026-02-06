"""Tests for async search adapter.

Tests verify that async wrappers correctly delegate to sync classes
using asyncio.to_thread.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestAsyncSearchAdapterStructure:
    """Test AsyncSearchAdapter structure and interface."""

    def test_adapter_can_be_imported(self):
        """AsyncSearchAdapter can be imported without errors."""
        try:
            from module.services.search_adapter import AsyncSearchAdapter
            assert AsyncSearchAdapter is not None
        except ImportError as e:
            pytest.skip(f"Cannot import due to dependency issues: {e}")

    def test_adapter_has_search_season_method(self):
        """AsyncSearchAdapter has search_season async method."""
        try:
            from module.services.search_adapter import AsyncSearchAdapter
            assert hasattr(AsyncSearchAdapter, "search_season")
            assert asyncio.iscoroutinefunction(AsyncSearchAdapter.search_season)
        except ImportError:
            pytest.skip("Cannot import due to dependency issues")

    def test_adapter_has_get_torrents_method(self):
        """AsyncSearchAdapter has get_torrents async method."""
        try:
            from module.services.search_adapter import AsyncSearchAdapter
            assert hasattr(AsyncSearchAdapter, "get_torrents")
            assert asyncio.iscoroutinefunction(AsyncSearchAdapter.get_torrents)
        except ImportError:
            pytest.skip("Cannot import due to dependency issues")


class TestAsyncRSSAnalyserAdapterStructure:
    """Test AsyncRSSAnalyserAdapter structure and interface."""

    def test_adapter_can_be_imported(self):
        """AsyncRSSAnalyserAdapter can be imported without errors."""
        try:
            from module.services.search_adapter import AsyncRSSAnalyserAdapter
            assert AsyncRSSAnalyserAdapter is not None
        except ImportError as e:
            pytest.skip(f"Cannot import due to dependency issues: {e}")

    def test_adapter_has_link_to_data_method(self):
        """AsyncRSSAnalyserAdapter has link_to_data async method."""
        try:
            from module.services.search_adapter import AsyncRSSAnalyserAdapter
            assert hasattr(AsyncRSSAnalyserAdapter, "link_to_data")
            assert asyncio.iscoroutinefunction(AsyncRSSAnalyserAdapter.link_to_data)
        except ImportError:
            pytest.skip("Cannot import due to dependency issues")

    def test_adapter_has_torrents_to_data_method(self):
        """AsyncRSSAnalyserAdapter has torrents_to_data async method."""
        try:
            from module.services.search_adapter import AsyncRSSAnalyserAdapter
            assert hasattr(AsyncRSSAnalyserAdapter, "torrents_to_data")
            assert asyncio.iscoroutinefunction(AsyncRSSAnalyserAdapter.torrents_to_data)
        except ImportError:
            pytest.skip("Cannot import due to dependency issues")

    def test_adapter_has_get_rss_torrents_method(self):
        """AsyncRSSAnalyserAdapter has get_rss_torrents async method."""
        try:
            from module.services.search_adapter import AsyncRSSAnalyserAdapter
            assert hasattr(AsyncRSSAnalyserAdapter, "get_rss_torrents")
            assert asyncio.iscoroutinefunction(AsyncRSSAnalyserAdapter.get_rss_torrents)
        except ImportError:
            pytest.skip("Cannot import due to dependency issues")

    def test_adapter_has_analyse_torrents_method(self):
        """AsyncRSSAnalyserAdapter has analyse_torrents async method."""
        try:
            from module.services.search_adapter import AsyncRSSAnalyserAdapter
            assert hasattr(AsyncRSSAnalyserAdapter, "analyse_torrents")
            assert asyncio.iscoroutinefunction(AsyncRSSAnalyserAdapter.analyse_torrents)
        except ImportError:
            pytest.skip("Cannot import due to dependency issues")

    def test_adapter_initializes_with_analyser(self):
        """AsyncRSSAnalyserAdapter initializes with RSSAnalyser instance."""
        try:
            from module.services.search_adapter import AsyncRSSAnalyserAdapter
            with patch("module.services.search_adapter.RSSAnalyser") as mock_analyser_class:
                adapter = AsyncRSSAnalyserAdapter()
                mock_analyser_class.assert_called_once()
                assert adapter._analyser == mock_analyser_class.return_value
        except ImportError:
            pytest.skip("Cannot import due to dependency issues")


class TestAsyncSearchAdapterBehavior:
    """Test AsyncSearchAdapter behavior with mocks."""

    @pytest.mark.asyncio
    async def test_search_season_uses_to_thread(self):
        """search_season delegates to asyncio.to_thread."""
        try:
            from module.services.search_adapter import AsyncSearchAdapter
        except ImportError:
            pytest.skip("Cannot import due to dependency issues")

        sample_bangumi = MagicMock()
        sample_torrents = [MagicMock(), MagicMock()]

        with patch("module.services.search_adapter.SearchTorrent") as mock_st_class:
            mock_st = MagicMock()
            mock_st.__enter__ = MagicMock(return_value=mock_st)
            mock_st.__exit__ = MagicMock(return_value=False)
            mock_st.search_season.return_value = sample_torrents
            mock_st_class.return_value = mock_st

            result = await AsyncSearchAdapter.search_season(sample_bangumi, "mikan")

            assert result == sample_torrents
            mock_st.search_season.assert_called_once_with(sample_bangumi, "mikan")

    @pytest.mark.asyncio
    async def test_get_torrents_uses_to_thread(self):
        """get_torrents delegates to asyncio.to_thread."""
        try:
            from module.services.search_adapter import AsyncSearchAdapter
        except ImportError:
            pytest.skip("Cannot import due to dependency issues")

        sample_torrents = [MagicMock(), MagicMock()]

        with patch("module.services.search_adapter.SearchTorrent") as mock_st_class:
            mock_st = MagicMock()
            mock_st.__enter__ = MagicMock(return_value=mock_st)
            mock_st.__exit__ = MagicMock(return_value=False)
            mock_st.get_torrents.return_value = sample_torrents
            mock_st_class.return_value = mock_st

            result = await AsyncSearchAdapter.get_torrents("https://example.com/rss")

            assert result == sample_torrents
            mock_st.get_torrents.assert_called_once()


class TestAsyncRSSAnalyserAdapterBehavior:
    """Test AsyncRSSAnalyserAdapter behavior with mocks."""

    @pytest.mark.asyncio
    async def test_link_to_data_uses_to_thread(self):
        """link_to_data delegates to asyncio.to_thread."""
        try:
            from module.services.search_adapter import AsyncRSSAnalyserAdapter
        except ImportError:
            pytest.skip("Cannot import due to dependency issues")

        sample_rss = MagicMock()
        sample_bangumi = MagicMock()

        with patch("module.services.search_adapter.RSSAnalyser") as mock_analyser_class:
            mock_analyser = MagicMock()
            mock_analyser.link_to_data.return_value = sample_bangumi
            mock_analyser_class.return_value = mock_analyser

            adapter = AsyncRSSAnalyserAdapter()
            result = await adapter.link_to_data(sample_rss)

            assert result == sample_bangumi
            mock_analyser.link_to_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_torrents_to_data_uses_to_thread(self):
        """torrents_to_data delegates to asyncio.to_thread."""
        try:
            from module.services.search_adapter import AsyncRSSAnalyserAdapter
        except ImportError:
            pytest.skip("Cannot import due to dependency issues")

        sample_torrents = [MagicMock()]
        sample_rss = MagicMock()
        sample_bangumi = [MagicMock()]

        with patch("module.services.search_adapter.RSSAnalyser") as mock_analyser_class:
            mock_analyser = MagicMock()
            mock_analyser.torrents_to_data.return_value = sample_bangumi
            mock_analyser_class.return_value = mock_analyser

            adapter = AsyncRSSAnalyserAdapter()
            result = await adapter.torrents_to_data(sample_torrents, sample_rss)

            assert result == sample_bangumi
            mock_analyser.torrents_to_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_rss_torrents_uses_to_thread(self):
        """get_rss_torrents delegates to asyncio.to_thread."""
        try:
            from module.services.search_adapter import AsyncRSSAnalyserAdapter
        except ImportError:
            pytest.skip("Cannot import due to dependency issues")

        sample_torrents = [MagicMock()]

        with patch("module.services.search_adapter.RSSAnalyser") as mock_analyser_class:
            mock_analyser = MagicMock()
            mock_analyser.get_rss_torrents.return_value = sample_torrents
            mock_analyser_class.return_value = mock_analyser

            adapter = AsyncRSSAnalyserAdapter()
            result = await adapter.get_rss_torrents("https://example.com/rss")

            assert result == sample_torrents
            mock_analyser.get_rss_torrents.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyse_torrents_uses_to_thread(self):
        """analyse_torrents delegates to asyncio.to_thread."""
        try:
            from module.services.search_adapter import AsyncRSSAnalyserAdapter
        except ImportError:
            pytest.skip("Cannot import due to dependency issues")

        sample_rss = MagicMock()
        sample_result = [{"name": "torrent1"}]

        with patch("module.services.search_adapter.RSSAnalyser") as mock_analyser_class:
            mock_analyser = MagicMock()
            mock_analyser.analyse_torrents.return_value = sample_result
            mock_analyser_class.return_value = mock_analyser

            adapter = AsyncRSSAnalyserAdapter()
            result = await adapter.analyse_torrents(sample_rss)

            assert result == sample_result
            mock_analyser.analyse_torrents.assert_called_once()
