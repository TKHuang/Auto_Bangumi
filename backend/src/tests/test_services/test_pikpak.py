"""TDD tests for PikPak downloader adapter.

Tests use mocked PikPakApi to verify pure async adapter behavior without
any threading or sync bridging.
"""

import json
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ...module.services.downloader.pikpak import PikPakDownloader


@pytest.fixture
def mock_pikpak_api():
    """Create a mock PikPakApi instance.

    Returns tuple of (MockClass, mock_instance) for configuring test behavior.
    """
    with patch("module.services.downloader.pikpak.PikPakApi") as MockApi:
        mock_instance = MagicMock()

        mock_instance.login = AsyncMock()
        mock_instance.refresh_access_token = AsyncMock()
        mock_instance.offline_download = AsyncMock(
            return_value={"task": {"id": "test_task_123"}}
        )
        mock_instance.offline_list = AsyncMock(return_value={"tasks": []})
        mock_instance.path_to_id = AsyncMock(
            return_value=[{"id": "folder_123", "name": "AutoBangumi"}]
        )
        mock_instance.file_list = AsyncMock(return_value={"files": []})
        mock_instance.file_rename = AsyncMock()
        mock_instance.delete_tasks = AsyncMock()
        mock_instance.delete_to_trash = AsyncMock()
        mock_instance.file_batch_move = AsyncMock()

        mock_instance.access_token = "test_access_token"
        mock_instance.refresh_token = "test_refresh_token"
        mock_instance.user_id = "test_user_123"
        mock_instance.encode_token = MagicMock()
        mock_instance.PIKPAK_API_HOST = "api-drive.mypikpak.com"
        mock_instance.get_headers = MagicMock(return_value={"Authorization": "Bearer test"})
        mock_instance.httpx_client = AsyncMock()
        mock_instance.httpx_client.request = AsyncMock()

        MockApi.return_value = mock_instance
        yield MockApi, mock_instance


@pytest.fixture
def temp_config_dir():
    """Create a temporary directory for config files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def mock_database():
    """Create a mock Database context manager."""
    with patch("module.services.downloader.pikpak.Database") as MockDatabase:
        mock_db_instance = MagicMock()
        mock_torrent_db = MagicMock()
        default_torrent = MagicMock()
        default_torrent.pikpak_cloud_path = "/downloads/Bangumi"
        default_torrent.renamed_at = None
        mock_torrent_db.search_by_hash = MagicMock(return_value=default_torrent)
        mock_db_instance.torrent = mock_torrent_db
        MockDatabase.return_value.__enter__ = MagicMock(
            return_value=mock_db_instance
        )
        MockDatabase.return_value.__exit__ = MagicMock(return_value=False)
        yield MockDatabase, mock_db_instance


@pytest.fixture
async def pikpak_downloader(mock_pikpak_api, mock_database, temp_config_dir):
    """Create a PikPakDownloader instance with mocked dependencies."""
    MockApi, mock_instance = mock_pikpak_api

    with patch(
        "module.services.downloader.pikpak.TOKEN_FILE",
        os.path.join(temp_config_dir, "pikpak_token.json"),
    ):
        downloader = PikPakDownloader("test@example.com", "password123")
        yield downloader


@pytest.fixture
async def pikpak_downloader_with_token(mock_pikpak_api, mock_database, temp_config_dir):
    """Create a PikPakDownloader with pre-existing valid token."""
    MockApi, mock_instance = mock_pikpak_api

    token_file = os.path.join(temp_config_dir, "pikpak_token.json")

    import time

    token_data = {
        "access_token": "existing_access_token",
        "refresh_token": "existing_refresh_token",
        "user_id": "existing_user_123",
        "expires_at": int(time.time()) + 7200,
    }
    os.makedirs(temp_config_dir, exist_ok=True)
    with open(token_file, "w") as f:
        json.dump(token_data, f)

    with patch("module.services.downloader.pikpak.TOKEN_FILE", token_file):
        downloader = PikPakDownloader("test@example.com", "password123")
        yield downloader


class TestPikPakDownloaderInit:
    """Tests for PikPakDownloader initialization."""

    @pytest.mark.asyncio
    async def test_init_without_token(self, pikpak_downloader, mock_pikpak_api):
        """Test initialization without existing token file."""
        _, mock_instance = mock_pikpak_api

        assert pikpak_downloader._username == "test@example.com"
        assert pikpak_downloader._client == mock_instance
        assert pikpak_downloader._token_expires_at == 0

    @pytest.mark.asyncio
    async def test_init_with_valid_token(
        self, pikpak_downloader_with_token, mock_pikpak_api
    ):
        """Test initialization loads existing valid token."""
        _, mock_instance = mock_pikpak_api

        assert mock_instance.access_token == "existing_access_token"
        assert mock_instance.refresh_token == "existing_refresh_token"
        assert mock_instance.user_id == "existing_user_123"
        assert mock_instance.encode_token.called

    @pytest.mark.asyncio
    async def test_init_with_expired_token(
        self, mock_pikpak_api, temp_config_dir, mock_database
    ):
        """Test initialization loads expired token."""
        MockApi, mock_instance = mock_pikpak_api

        token_file = os.path.join(temp_config_dir, "pikpak_token.json")

        import time

        token_data = {
            "access_token": "expired_token",
            "refresh_token": "expired_refresh",
            "user_id": "user_123",
            "expires_at": int(time.time()) - 100,
        }
        os.makedirs(temp_config_dir, exist_ok=True)
        with open(token_file, "w") as f:
            json.dump(token_data, f)

        with patch("module.services.downloader.pikpak.TOKEN_FILE", token_file):
            downloader = PikPakDownloader("test@example.com", "password123")

            assert downloader._token_expires_at == 0
            assert mock_instance.encode_token.called


class TestPikPakDownloaderAuth:
    """Tests for PikPakDownloader authentication."""

    @pytest.mark.asyncio
    async def test_auth_success(self, pikpak_downloader, mock_pikpak_api):
        """Test successful authentication."""
        _, mock_instance = mock_pikpak_api

        result = await pikpak_downloader.auth()

        assert result is True
        mock_instance.login.assert_called_once()
        assert pikpak_downloader._token_expires_at > 0

    @pytest.mark.asyncio
    async def test_auth_failure_propagates_exception(
        self, pikpak_downloader, mock_pikpak_api
    ):
        """Test authentication failure raises exception."""
        _, mock_instance = mock_pikpak_api
        mock_instance.login = AsyncMock(side_effect=Exception("Invalid credentials"))

        with pytest.raises(Exception, match="Invalid credentials"):
            await pikpak_downloader.auth()

    @pytest.mark.asyncio
    async def test_check_host_success(self, pikpak_downloader):
        """Test check_host returns True when API is reachable."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_class.return_value.__aexit__ = AsyncMock()

            result = await pikpak_downloader.check_host()

            assert result is True

    @pytest.mark.asyncio
    async def test_check_host_failure(self, pikpak_downloader):
        """Test check_host returns False when API is unreachable."""
        import httpx

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            mock_client_class.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_class.return_value.__aexit__ = AsyncMock()

            result = await pikpak_downloader.check_host()

            assert result is False

    @pytest.mark.asyncio
    async def test_logout_is_noop(self, pikpak_downloader):
        """Test logout does nothing (preserves tokens)."""
        pikpak_downloader._token_expires_at = 12345

        await pikpak_downloader.logout()

        assert pikpak_downloader._token_expires_at == 12345


class TestPikPakDownloaderTorrents:
    """Tests for torrent operations."""

    @pytest.mark.asyncio
    async def test_add_torrents_single_url(
        self, pikpak_downloader, mock_pikpak_api, mock_database
    ):
        """Test adding a single magnet URL."""
        _, mock_instance = mock_pikpak_api

        result = await pikpak_downloader.add_torrents(
            urls=["magnet:?xt=urn:btih:abc123def456abc123def456abc123def456abc1&dn=test"],
            save_path="Test Series/Season 1",
        )

        assert result is True
        mock_instance.offline_download.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_torrents_multiple_urls(
        self, pikpak_downloader, mock_pikpak_api
    ):
        """Test adding multiple magnet URLs."""
        _, mock_instance = mock_pikpak_api

        urls = [
            "magnet:?xt=urn:btih:1111111111111111111111111111111111111111&dn=ep1",
            "magnet:?xt=urn:btih:2222222222222222222222222222222222222222&dn=ep2",
        ]

        result = await pikpak_downloader.add_torrents(
            urls=urls, save_path="Test Series/Season 1"
        )

        assert result is True
        assert mock_instance.offline_download.call_count == 2

    @pytest.mark.asyncio
    async def test_add_torrents_no_urls_returns_false(self, pikpak_downloader):
        """Test add_torrents returns False when no URLs provided."""
        result = await pikpak_downloader.add_torrents(urls=None)
        assert result is False

    @pytest.mark.asyncio
    async def test_add_torrents_torrent_files_not_supported(
        self, pikpak_downloader, mock_pikpak_api
    ):
        """Test that torrent files are rejected."""
        result = await pikpak_downloader.add_torrents(
            urls=None, torrent_files=[b"fake torrent content"]
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_torrents_info_completed(self, pikpak_downloader, mock_pikpak_api):
        """Test getting info about completed torrents."""
        _, mock_instance = mock_pikpak_api
        mock_instance.offline_list = AsyncMock(
            return_value={
                "tasks": [
                    {
                        "id": "task_1",
                        "name": "Test Episode 01.mkv",
                        "phase": "PHASE_TYPE_COMPLETE",
                        "progress": 100,
                        "file_url": "magnet:?xt=urn:btih:abc123def456abc123def456abc123def456abc1",
                    }
                ]
            }
        )
        mock_instance.path_to_id = AsyncMock(
            return_value=[
                {"id": "folder_1", "name": "downloads"},
                {"id": "folder_2", "name": "Bangumi"},
            ]
        )
        mock_instance.file_list = AsyncMock(
            return_value={
                "files": [{"name": "Test Episode 01.mkv", "kind": "drive#file"}]
            }
        )

        result = await pikpak_downloader.torrents_info(status_filter="completed")

        assert len(result) == 1
        assert result[0].name == "Test Episode 01.mkv"
        assert result[0].state == "completed"
        assert result[0].progress == 1.0

    @pytest.mark.asyncio
    async def test_torrents_info_downloading(
        self, pikpak_downloader, mock_pikpak_api
    ):
        """Test getting info about downloading torrents."""
        _, mock_instance = mock_pikpak_api
        mock_instance.offline_list = AsyncMock(
            return_value={
                "tasks": [
                    {
                        "id": "task_1",
                        "name": "Downloading Episode.mkv",
                        "phase": "PHASE_TYPE_RUNNING",
                        "progress": 50,
                        "file_url": "magnet:?xt=urn:btih:abc123def456abc123def456abc123def456abc1",
                    }
                ]
            }
        )

        result = await pikpak_downloader.torrents_info(status_filter="downloading")

        assert len(result) == 1
        assert result[0].state == "downloading"
        assert result[0].progress == 0.5

    @pytest.mark.asyncio
    async def test_torrents_delete_single_hash(
        self, pikpak_downloader, mock_pikpak_api
    ):
        """Test deleting a single torrent by hash."""
        _, mock_instance = mock_pikpak_api
        mock_instance.offline_list = AsyncMock(
            return_value={
                "tasks": [
                    {
                        "id": "task_1",
                        "file_url": "magnet:?xt=urn:btih:abc123def456abc123def456abc123def456abc1",
                    }
                ]
            }
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_instance.httpx_client.request = AsyncMock(return_value=mock_response)

        result = await pikpak_downloader.torrents_delete(
            ["abc123def456abc123def456abc123def456abc1"]
        )

        assert result is True
        mock_instance.offline_list.assert_called()

    @pytest.mark.asyncio
    async def test_torrents_delete_multiple_hashes(
        self, pikpak_downloader, mock_pikpak_api
    ):
        """Test deleting multiple torrents."""
        _, mock_instance = mock_pikpak_api
        mock_instance.offline_list = AsyncMock(return_value={"tasks": []})

        hashes = [
            "1111111111111111111111111111111111111111",
            "2222222222222222222222222222222222222222",
        ]

        result = await pikpak_downloader.torrents_delete(hashes)

        assert result is True
        assert mock_instance.offline_list.call_count >= 2

    @pytest.mark.asyncio
    async def test_get_existing_hashes(self, pikpak_downloader, mock_pikpak_api):
        """Test getting existing torrent hashes."""
        _, mock_instance = mock_pikpak_api
        mock_instance.offline_list = AsyncMock(
            return_value={
                "tasks": [
                    {
                        "id": "task_1",
                        "file_url": "magnet:?xt=urn:btih:abc123def456abc123def456abc123def456abc1",
                    },
                    {
                        "id": "task_2",
                        "file_url": "magnet:?xt=urn:btih:def456abc123def456abc123def456abc12345ef",
                    },
                ]
            }
        )

        result = await pikpak_downloader.get_existing_hashes()

        assert len(result) == 2
        assert "abc123def456abc123def456abc123def456abc1" in result
        assert "def456abc123def456abc123def456abc12345ef" in result


class TestPikPakDownloaderHashExtraction:
    """Tests for torrent hash extraction from magnet links."""

    @pytest.mark.asyncio
    async def test_extract_hash_from_magnet(self, pikpak_downloader):
        """Test extracting hash from standard magnet link."""
        url = "magnet:?xt=urn:btih:abc123def456abc123def456abc123def456abc1&dn=test"
        result = pikpak_downloader._extract_hash(url)
        assert result == "abc123def456abc123def456abc123def456abc1"

    @pytest.mark.asyncio
    async def test_extract_hash_case_insensitive(self, pikpak_downloader):
        """Test hash extraction is case insensitive."""
        url = "magnet:?xt=URN:BTIH:ABC123DEF456ABC123DEF456ABC123DEF456ABC1&dn=test"
        result = pikpak_downloader._extract_hash(url)
        assert result.lower() == "abc123def456abc123def456abc123def456abc1"

    @pytest.mark.asyncio
    async def test_extract_hash_no_match(self, pikpak_downloader):
        """Test hash extraction returns None for invalid URLs."""
        result = pikpak_downloader._extract_hash("https://example.com/not-a-magnet")
        assert result is None


class TestPikPakDownloaderTokenRefresh:
    """Tests for token refresh mechanism."""

    @pytest.mark.asyncio
    async def test_ensure_valid_token_valid(
        self, pikpak_downloader_with_token, mock_pikpak_api
    ):
        """Test _ensure_valid_token does nothing when token is valid."""
        _, mock_instance = mock_pikpak_api

        await pikpak_downloader_with_token._ensure_valid_token()

        mock_instance.refresh_access_token.assert_not_called()
        mock_instance.login.assert_not_called()

    @pytest.mark.asyncio
    async def test_ensure_valid_token_expires_soon(
        self, pikpak_downloader, mock_pikpak_api
    ):
        """Test _ensure_valid_token refreshes when token expires soon."""
        _, mock_instance = mock_pikpak_api
        import time

        pikpak_downloader._token_expires_at = int(time.time()) + 120
        pikpak_downloader._client.refresh_token = "test_refresh"

        await pikpak_downloader._ensure_valid_token()

        mock_instance.refresh_access_token.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_valid_token_no_refresh_token(
        self, pikpak_downloader, mock_pikpak_api
    ):
        """Test _ensure_valid_token re-authenticates when no refresh token."""
        _, mock_instance = mock_pikpak_api
        import time

        pikpak_downloader._token_expires_at = int(time.time()) - 100
        pikpak_downloader._client.refresh_token = None

        await pikpak_downloader._ensure_valid_token()

        mock_instance.login.assert_called_once()


class TestStalePathDetection:
    """Tests for stale path detection in _list_files_in_folder."""

    @pytest.mark.asyncio
    async def test_stale_path_returns_empty_list(
        self, pikpak_downloader, mock_pikpak_api
    ):
        """Test that partial path resolution returns empty list."""
        _, mock_instance = mock_pikpak_api

        mock_instance.path_to_id = AsyncMock(
            return_value=[{"id": "bangumi_id", "name": "Bangumi"}]
        )

        mock_instance.file_list = AsyncMock(
            return_value={
                "files": [
                    {"name": "Anime1", "kind": "drive#folder", "id": "a1"},
                    {"name": "Anime2", "kind": "drive#folder", "id": "a2"},
                    {"name": "video.mp4", "kind": "drive#file", "id": "v1"},
                ]
            }
        )

        files = await pikpak_downloader._list_files_in_folder(
            "/Bangumi/Title/Season 4"
        )

        assert files == []
        mock_instance.file_list.assert_not_called()

    @pytest.mark.asyncio
    async def test_valid_path_returns_files(self, pikpak_downloader, mock_pikpak_api):
        """Test that full path resolution works normally."""
        _, mock_instance = mock_pikpak_api

        mock_instance.path_to_id = AsyncMock(
            return_value=[
                {"id": "bangumi_id", "name": "Bangumi"},
                {"id": "title_id", "name": "Title"},
                {"id": "season_id", "name": "Season 4"},
            ]
        )

        mock_instance.file_list = AsyncMock(
            return_value={
                "files": [
                    {"name": "episode01.mkv", "kind": "drive#file", "id": "e1"},
                    {"name": "episode02.mkv", "kind": "drive#file", "id": "e2"},
                ]
            }
        )

        files = await pikpak_downloader._list_files_in_folder(
            "/Bangumi/Title/Season 4"
        )

        assert len(files) == 2
        assert files[0].name == "episode01.mkv"
        assert files[1].name == "episode02.mkv"
        mock_instance.file_list.assert_called_once_with(parent_id="season_id")


class TestPikPakAsyncBehavior:
    """Tests verifying pure async behavior without threading."""

    @pytest.mark.asyncio
    async def test_auth_is_async(self, pikpak_downloader):
        """Test that auth method is async."""
        import inspect

        assert inspect.iscoroutinefunction(pikpak_downloader.auth)

    @pytest.mark.asyncio
    async def test_add_torrents_is_async(self, pikpak_downloader):
        """Test that add_torrents method is async."""
        import inspect

        assert inspect.iscoroutinefunction(pikpak_downloader.add_torrents)

    @pytest.mark.asyncio
    async def test_torrents_info_is_async(self, pikpak_downloader):
        """Test that torrents_info method is async."""
        import inspect

        assert inspect.iscoroutinefunction(pikpak_downloader.torrents_info)

    @pytest.mark.asyncio
    async def test_torrents_delete_is_async(self, pikpak_downloader):
        """Test that torrents_delete method is async."""
        import inspect

        assert inspect.iscoroutinefunction(pikpak_downloader.torrents_delete)

    @pytest.mark.asyncio
    async def test_move_torrent_is_async(self, pikpak_downloader):
        """Test that move_torrent method is async."""
        import inspect

        assert inspect.iscoroutinefunction(pikpak_downloader.move_torrent)


class TestPikPakClassAttributes:
    """Tests for class-level attributes."""

    @pytest.mark.asyncio
    async def test_supports_torrent_files_is_false(self):
        """Test that supports_torrent_files is False for PikPak."""
        assert PikPakDownloader.supports_torrent_files is False
