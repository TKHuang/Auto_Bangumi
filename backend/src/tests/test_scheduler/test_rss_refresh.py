"""Tests for RSS refresh scheduled job."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from module.scheduler.jobs.rss_refresh import rss_refresh_job


class TestRSSRefreshJob:
    """Test RSS refresh job execution."""

    @pytest.mark.asyncio
    async def test_rss_refresh_job_success(self):
        """Test successful RSS refresh job execution."""
        mock_session = AsyncMock()
        mock_downloader = MagicMock()
        mock_session_gen = AsyncMock()
        mock_session_gen.__anext__.return_value = mock_session

        with patch("module.scheduler.jobs.rss_refresh.get_db_session") as mock_get_db:
            with patch(
                "module.scheduler.jobs.rss_refresh.create_downloader"
            ) as mock_create_dl:
                with patch(
                    "module.scheduler.jobs.rss_refresh.RSSEngine.refresh_all_rss"
                ) as mock_refresh:
                    mock_get_db.return_value = mock_session_gen
                    mock_create_dl.return_value = mock_downloader
                    mock_refresh.return_value = None

                    await rss_refresh_job()

                    mock_get_db.assert_called_once()
                    mock_session_gen.__anext__.assert_called_once()
                    mock_create_dl.assert_called_once()
                    mock_refresh.assert_called_once_with(mock_session, mock_downloader)
                    mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_rss_refresh_job_error_handling(self):
        """Test that errors in refresh don't crash scheduler."""
        mock_session = AsyncMock()
        mock_session_gen = AsyncMock()
        mock_session_gen.__anext__.return_value = mock_session

        with patch("module.scheduler.jobs.rss_refresh.get_db_session") as mock_get_db:
            with patch(
                "module.scheduler.jobs.rss_refresh.create_downloader"
            ) as mock_create_dl:
                with patch(
                    "module.scheduler.jobs.rss_refresh.RSSEngine.refresh_all_rss"
                ) as mock_refresh:
                    mock_get_db.return_value = mock_session_gen
                    mock_create_dl.return_value = MagicMock()
                    mock_refresh.side_effect = Exception("Network error")

                    # Should not raise - error is caught and logged
                    await rss_refresh_job()

                    mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_rss_refresh_job_session_cleanup_on_error(self):
        """Test that session is cleaned up even if refresh fails."""
        mock_session = AsyncMock()
        mock_session_gen = AsyncMock()
        mock_session_gen.__anext__.return_value = mock_session

        with patch("module.scheduler.jobs.rss_refresh.get_db_session") as mock_get_db:
            with patch(
                "module.scheduler.jobs.rss_refresh.create_downloader"
            ) as mock_create_dl:
                with patch(
                    "module.scheduler.jobs.rss_refresh.RSSEngine.refresh_all_rss"
                ) as mock_refresh:
                    mock_get_db.return_value = mock_session_gen
                    mock_create_dl.return_value = MagicMock()
                    mock_refresh.side_effect = RuntimeError("Refresh failed")

                    await rss_refresh_job()

                    # Session should be closed even on error
                    mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_rss_refresh_job_downloader_creation(self):
        """Test that downloader is created with settings."""
        mock_session = AsyncMock()
        mock_session_gen = AsyncMock()
        mock_session_gen.__anext__.return_value = mock_session

        with patch("module.scheduler.jobs.rss_refresh.get_db_session") as mock_get_db:
            with patch(
                "module.scheduler.jobs.rss_refresh.create_downloader"
            ) as mock_create_dl:
                with patch(
                    "module.scheduler.jobs.rss_refresh.RSSEngine.refresh_all_rss"
                ) as mock_refresh:
                    with patch(
                        "module.scheduler.jobs.rss_refresh.settings"
                    ) as mock_settings:
                        mock_get_db.return_value = mock_session_gen
                        mock_create_dl.return_value = MagicMock()
                        mock_refresh.return_value = None

                        await rss_refresh_job()

                        mock_create_dl.assert_called_once_with(mock_settings)
