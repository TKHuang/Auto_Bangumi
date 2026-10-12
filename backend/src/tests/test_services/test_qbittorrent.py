"""TDD tests for qBittorrent downloader adapter.

Tests use mocked qbittorrent-api Client to verify async adapter behavior.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from qbittorrentapi import LoginFailed
from qbittorrentapi.exceptions import (
    APIConnectionError,
    Conflict409Error,
    Forbidden403Error,
)

from module.services.downloader.interface import RenameOutcome
from module.services.downloader.qbittorrent import QBittorrentDownloader


@pytest.fixture
def mock_qb_client():
    """Create a mocked qBittorrent Client."""
    client = MagicMock()
    client.auth_log_in = MagicMock()
    client.auth_log_out = MagicMock()
    client.app_version = MagicMock(return_value="v4.5.0")
    client.torrents_add = MagicMock(return_value="Ok.")
    client.torrents_info = MagicMock(return_value=[])
    client.torrents_rename_file = MagicMock()
    client.torrents_delete = MagicMock()
    client.torrents_set_location = MagicMock()
    return client


@pytest.fixture
def downloader(mock_qb_client):
    """Create QBittorrentDownloader with mocked client."""
    with patch("module.services.downloader.qbittorrent.Client", return_value=mock_qb_client):
        dl = QBittorrentDownloader(
            host="http://localhost:8080",
            username="admin",
            password="adminpass",
            ssl=False,
        )
        return dl


class TestQBittorrentAuth:
    """Test authentication and connection."""

    @pytest.fixture(autouse=True)
    def _no_retry_sleep(self):
        with patch("module.services.downloader.qbittorrent.asyncio.sleep", AsyncMock()):
            yield

    @pytest.mark.asyncio
    async def test_auth_success(self, downloader, mock_qb_client):
        """Auth succeeds on first attempt."""
        mock_qb_client.auth_log_in.return_value = None
        result = await downloader.auth()
        assert result is True
        mock_qb_client.auth_log_in.assert_called_once()

    @pytest.mark.asyncio
    async def test_auth_retry_on_login_failed(self, downloader, mock_qb_client):
        """Auth retries 3 times on LoginFailed."""
        mock_qb_client.auth_log_in.side_effect = [
            LoginFailed("Bad credentials"),
            LoginFailed("Bad credentials"),
            None,  # Success on 3rd attempt
        ]
        result = await downloader.auth(retry=3)
        assert result is True
        assert mock_qb_client.auth_log_in.call_count == 3

    @pytest.mark.asyncio
    async def test_auth_fails_after_retries(self, downloader, mock_qb_client):
        """Auth fails after exhausting retries."""
        mock_qb_client.auth_log_in.side_effect = LoginFailed("Bad credentials")
        result = await downloader.auth(retry=3)
        assert result is False
        assert mock_qb_client.auth_log_in.call_count == 3

    @pytest.mark.asyncio
    async def test_auth_forbidden_403(self, downloader, mock_qb_client):
        """Auth stops immediately on Forbidden403Error."""
        mock_qb_client.auth_log_in.side_effect = Forbidden403Error("IP banned")
        result = await downloader.auth(retry=3)
        assert result is False
        assert mock_qb_client.auth_log_in.call_count == 1  # No retry

    @pytest.mark.asyncio
    async def test_auth_connection_error_retry(self, downloader, mock_qb_client):
        """Auth retries on APIConnectionError."""
        mock_qb_client.auth_log_in.side_effect = [
            APIConnectionError("Connection refused"),
            None,  # Success on 2nd attempt
        ]
        result = await downloader.auth(retry=3)
        assert result is True
        assert mock_qb_client.auth_log_in.call_count == 2

    @pytest.mark.asyncio
    async def test_check_host_success(self, downloader, mock_qb_client):
        """check_host returns True when app_version succeeds."""
        mock_qb_client.app_version.return_value = "v4.5.0"
        result = await downloader.check_host()
        assert result is True

    @pytest.mark.asyncio
    async def test_check_host_failure(self, downloader, mock_qb_client):
        """check_host returns False on APIConnectionError."""
        mock_qb_client.app_version.side_effect = APIConnectionError("Unreachable")
        result = await downloader.check_host()
        assert result is False


class TestQBittorrentTorrents:
    """Test torrent operations."""

    @pytest.mark.asyncio
    async def test_add_torrents_success(self, downloader, mock_qb_client):
        """add_torrents returns True when API returns 'Ok.'"""
        mock_qb_client.torrents_add.return_value = "Ok."
        result = await downloader.add_torrents(
            urls=["magnet:?xt=urn:btih:abc123"],
            save_path="/downloads/bangumi",
        )
        assert result is True
        mock_qb_client.torrents_add.assert_called_once_with(
            is_paused=False,
            urls=["magnet:?xt=urn:btih:abc123"],
            torrent_files=None,
            save_path="/downloads/bangumi",
            category="Bangumi",
            use_auto_torrent_management=False,
            content_layout="NoSubFolder",
        )

    @pytest.mark.asyncio
    async def test_add_torrents_with_files(self, downloader, mock_qb_client):
        """add_torrents accepts torrent_files parameter."""
        mock_qb_client.torrents_add.return_value = "Ok."
        torrent_data = [b"fake torrent file content"]
        result = await downloader.add_torrents(
            torrent_files=torrent_data,
            save_path="/downloads/bangumi",
        )
        assert result is True
        mock_qb_client.torrents_add.assert_called_once_with(
            is_paused=False,
            urls=None,
            torrent_files=torrent_data,
            save_path="/downloads/bangumi",
            category="Bangumi",
            use_auto_torrent_management=False,
            content_layout="NoSubFolder",
        )

    @pytest.mark.asyncio
    async def test_add_torrents_failure(self, downloader, mock_qb_client):
        """add_torrents returns False when API returns non-Ok response."""
        mock_qb_client.torrents_add.return_value = "Fails."
        result = await downloader.add_torrents(
            urls=["magnet:?xt=urn:btih:abc123"],
            save_path="/downloads/bangumi",
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_torrents_info_maps_states(self, downloader, mock_qb_client):
        """torrents_info maps qBittorrent states to TorrentInfo."""
        mock_torrent = MagicMock()
        mock_torrent.hash = "abc123"
        mock_torrent.name = "Test Bangumi S01E01"
        mock_torrent.state = "downloading"
        mock_torrent.progress = 0.45
        mock_torrent.save_path = "/downloads/bangumi"
        mock_torrent.size = 1024 * 1024 * 500  # 500MB
        mock_torrent.files = []

        mock_qb_client.torrents_info.return_value = [mock_torrent]

        result = await downloader.torrents_info(
            status_filter="downloading",
            category="Bangumi",
        )

        assert len(result) == 1
        assert result[0].hash == "abc123"
        assert result[0].name == "Test Bangumi S01E01"
        assert result[0].state == "downloading"
        assert result[0].progress == 0.45
        assert result[0].save_path == "/downloads/bangumi"
        assert result[0].size == 1024 * 1024 * 500

    @pytest.mark.asyncio
    async def test_torrents_rename_file_success(self, downloader, mock_qb_client):
        """torrents_rename_file returns True on success."""
        mock_qb_client.torrents_rename_file.return_value = None
        result = await downloader.torrents_rename_file(
            hash="abc123",
            old_path="old_name.mp4",
            new_path="new_name.mp4",
        )
        assert result is RenameOutcome.OK
        mock_qb_client.torrents_rename_file.assert_called_once_with(
            torrent_hash="abc123",
            old_path="old_name.mp4",
            new_path="new_name.mp4",
        )

    @pytest.mark.asyncio
    async def test_torrents_rename_file_conflict(self, downloader, mock_qb_client):
        """torrents_rename_file returns CONFLICT on Conflict409Error."""
        mock_qb_client.torrents_rename_file.side_effect = Conflict409Error("Already exists")
        result = await downloader.torrents_rename_file(
            hash="abc123",
            old_path="old_name.mp4",
            new_path="new_name.mp4",
        )
        assert result is RenameOutcome.CONFLICT

    @pytest.mark.asyncio
    async def test_torrents_delete_with_files(self, downloader, mock_qb_client):
        """torrents_delete deletes torrents and files."""
        mock_qb_client.torrents_delete.return_value = None
        result = await downloader.torrents_delete(
            hashes=["abc123", "def456"],
            delete_files=True,
        )
        assert result is True
        mock_qb_client.torrents_delete.assert_called_once_with(
            delete_files=True,
            torrent_hashes=["abc123", "def456"],
        )

    @pytest.mark.asyncio
    async def test_torrents_delete_keep_files(self, downloader, mock_qb_client):
        """torrents_delete can keep files."""
        mock_qb_client.torrents_delete.return_value = None
        result = await downloader.torrents_delete(
            hashes=["abc123"],
            delete_files=False,
        )
        assert result is True
        mock_qb_client.torrents_delete.assert_called_once_with(
            delete_files=False,
            torrent_hashes=["abc123"],
        )

    @pytest.mark.asyncio
    async def test_move_torrent(self, downloader, mock_qb_client):
        """move_torrent sets new location."""
        mock_qb_client.torrents_set_location.return_value = None
        result = await downloader.move_torrent(
            hashes=["abc123"],
            new_location="/new/path",
        )
        assert result is True
        mock_qb_client.torrents_set_location.assert_called_once_with(
            "/new/path",
            ["abc123"],
        )
