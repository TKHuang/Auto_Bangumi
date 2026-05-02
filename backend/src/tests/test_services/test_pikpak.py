"""TDD tests for PikPak downloader adapter.

Tests use mocked PikPakApi to verify pure async adapter behavior without
any threading or sync bridging.
"""

import json
import logging
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from module.services.downloader.pikpak import PikPakDownloader


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
    """Create a mock TorrentRepository for PikPak tests."""
    with patch("module.services.downloader.pikpak.TorrentRepository") as MockRepo:
        mock_repo_instance = AsyncMock()
        default_torrent = MagicMock()
        default_torrent.pikpak_cloud_path = "/downloads/Bangumi"
        default_torrent.renamed_at = None
        mock_repo_instance.get_by_hash = AsyncMock(return_value=default_torrent)
        MockRepo.return_value = mock_repo_instance
        yield MockRepo, mock_repo_instance


@pytest.fixture
async def pikpak_downloader(mock_pikpak_api, mock_database, temp_config_dir):
    """Create a PikPakDownloader instance with mocked dependencies."""
    MockApi, mock_instance = mock_pikpak_api

    with patch(
        "module.services.downloader.pikpak.TOKEN_FILE",
        os.path.join(temp_config_dir, "pikpak_token.json"),
    ):
        mock_session = AsyncMock()
        downloader = PikPakDownloader("test@example.com", "password123", session=mock_session)
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
        mock_session = AsyncMock()
        downloader = PikPakDownloader("test@example.com", "password123", session=mock_session)
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
        """Test successful authentication.

        With the new _ensure_valid_token flow, auth() tries refresh first
        (since mock client has a truthy refresh_token). If refresh succeeds,
        login is never called.
        """
        _, mock_instance = mock_pikpak_api

        result = await pikpak_downloader.auth()

        assert result is True
        mock_instance.refresh_access_token.assert_called_once()

    @pytest.mark.asyncio
    async def test_auth_failure_propagates_exception(
        self, pikpak_downloader, mock_pikpak_api
    ):
        """Test authentication failure raises exception.

        Both refresh and login must fail for auth() to propagate the error,
        since _ensure_valid_token tries refresh first then falls through to login.
        """
        _, mock_instance = mock_pikpak_api
        mock_instance.refresh_access_token = AsyncMock(
            side_effect=Exception("Refresh failed")
        )
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

        with patch("module.services.downloader.pikpak.httpx.AsyncClient") as mock_client_class:
            # Create a mock that raises an exception when get() is called
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            # Make the mock work as an async context manager
            mock_client_class.return_value = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

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
    async def test_torrents_info_treats_task_file_deleted_with_files_as_completed(
        self, pikpak_downloader, mock_pikpak_api
    ):
        """Treat stale PikPak task as completed when files still exist in save_path."""
        _, mock_instance = mock_pikpak_api
        target_hash = "abc123def456abc123def456abc123def456abc1"
        mock_instance.offline_list = AsyncMock(
            return_value={
                "tasks": [
                    {
                        "id": "task_1",
                        "name": "Collection [01-12]",
                        "file_name": "Collection [01-12]",
                        "phase": "PHASE_TYPE_ERROR",
                        "message": "File deleted",
                        "progress": 100,
                        "file_url": f"magnet:?xt=urn:btih:{target_hash}",
                        "params": {"error_detail": "task_file_deleted"},
                    }
                ]
            }
        )
        mock_instance.path_to_id = AsyncMock(
            return_value=[
                {"id": "dl_id", "name": "downloads"},
                {"id": "bg_id", "name": "Bangumi"},
                {"id": "season_id", "name": "Season 1"},
            ]
        )
        mock_instance.file_list = AsyncMock(
            return_value={
                "files": [
                    {"name": "Episode 01.mkv", "kind": "drive#file", "id": "e1"},
                    {"name": "Episode 02.mkv", "kind": "drive#file", "id": "e2"},
                ]
            }
        )

        result = await pikpak_downloader.torrents_info(status_filter="all")

        assert len(result) == 1
        assert result[0].state == "completed"
        assert len(result[0].files) == 2

    @pytest.mark.asyncio
    async def test_torrents_info_task_file_deleted_single_file_ignores_other_episode_root_files(
        self, pikpak_downloader, mock_pikpak_api
    ):
        """Single-episode deleted task should not reuse unrelated season files."""
        _, mock_instance = mock_pikpak_api
        target_hash = "abc123def456abc123def456abc123def456abc1"
        mock_instance.offline_list = AsyncMock(
            return_value={
                "tasks": [
                    {
                        "id": "task_1",
                        "name": "[LoliHouse] Nigetsuri - 04 [1080p].mkv",
                        "file_name": "[LoliHouse] Nigetsuri - 04 [1080p].mkv",
                        "phase": "PHASE_TYPE_ERROR",
                        "message": "File deleted",
                        "progress": 100,
                        "file_url": f"magnet:?xt=urn:btih:{target_hash}",
                        "params": {"error_detail": "task_file_deleted"},
                    }
                ]
            }
        )
        mock_instance.path_to_id = AsyncMock(
            return_value=[
                {"id": "dl_id", "name": "downloads"},
                {"id": "bg_id", "name": "Bangumi"},
            ]
        )
        mock_instance.file_list = AsyncMock(
            return_value={
                "files": [
                    {"name": "Nigetsuri S01E01.mkv", "kind": "drive#file", "id": "e1"},
                    {"name": "Nigetsuri S01E02.mkv", "kind": "drive#file", "id": "e2"},
                    {"name": "Nigetsuri S01E03.mkv", "kind": "drive#file", "id": "e3"},
                ]
            }
        )

        result = await pikpak_downloader.torrents_info(status_filter="all")

        assert len(result) == 1
        assert result[0].state == "error"
        assert result[0].files == []

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
        mock_instance.offline_list.assert_called()

    @pytest.mark.asyncio
    async def test_torrents_delete_deletes_all_matching_task_ids(
        self, pikpak_downloader, mock_pikpak_api
    ):
        """Test delete removes every PikPak task sharing the same torrent hash."""
        _, mock_instance = mock_pikpak_api
        target_hash = "abc123def456abc123def456abc123def456abc1"
        mock_instance.offline_list = AsyncMock(
            return_value={
                "tasks": [
                    {
                        "id": "task_1",
                        "name": "Episode 01",
                        "file_url": f"magnet:?xt=urn:btih:{target_hash}",
                    },
                    {
                        "id": "task_2",
                        "name": "Episode 01 duplicate",
                        "file_url": f"magnet:?xt=urn:btih:{target_hash}",
                    },
                ]
            }
        )

        mock_response = MagicMock(status_code=200, text="OK")
        mock_instance.httpx_client.request = AsyncMock(return_value=mock_response)

        result = await pikpak_downloader.torrents_delete([target_hash], delete_files=False)

        assert result is True
        mock_instance.httpx_client.request.assert_awaited_once()
        _, kwargs = mock_instance.httpx_client.request.await_args
        assert kwargs["params"]["task_ids"] == "task_1,task_2"
        assert kwargs["params"]["delete_files"] == "false"

    @pytest.mark.asyncio
    async def test_torrents_delete_fallback_cleans_lingering_direct_file(
        self, pikpak_downloader, mock_pikpak_api
    ):
        """Test delete_files cleans direct file residue when task delete leaves files behind."""
        _, mock_instance = mock_pikpak_api
        target_hash = "abc123def456abc123def456abc123def456abc1"
        task_name = "Episode 01.mkv"

        mock_instance.offline_list = AsyncMock(
            return_value={
                "tasks": [
                    {
                        "id": "task_1",
                        "name": task_name,
                        "file_name": task_name,
                        "phase": "PHASE_TYPE_ERROR",
                        "file_url": f"magnet:?xt=urn:btih:{target_hash}",
                    }
                ]
            }
        )

        mock_response = MagicMock(status_code=200, text="OK")
        mock_instance.httpx_client.request = AsyncMock(return_value=mock_response)
        mock_instance.path_to_id = AsyncMock(
            side_effect=[
                [{"id": "season_id", "name": "downloads/Bangumi/Season 1"}],
                [{"id": "season_id", "name": "downloads/Bangumi/Season 1"}],
            ]
        )
        mock_instance.file_list = AsyncMock(
            return_value={
                "files": [
                    {
                        "id": "file_1",
                        "name": task_name,
                        "kind": "drive#file",
                    }
                ]
            }
        )

        result = await pikpak_downloader.torrents_delete([target_hash], delete_files=True)

        assert result is True
        mock_instance.delete_to_trash.assert_awaited_once_with(ids=["file_1"])

    @pytest.mark.asyncio
    async def test_torrents_delete_fallback_uses_task_file_id_when_present(
        self, pikpak_downloader, mock_pikpak_api
    ):
        """Test delete_files prefers raw PikPak file_id for lingering cleanup."""
        _, mock_instance = mock_pikpak_api
        target_hash = "abc123def456abc123def456abc123def456abc1"

        mock_instance.offline_list = AsyncMock(
            return_value={
                "tasks": [
                    {
                        "id": "task_1",
                        "name": "Collection [01-12]",
                        "file_name": "Collection [01-12]",
                        "file_id": "folder_123",
                        "phase": "PHASE_TYPE_ERROR",
                        "file_url": f"magnet:?xt=urn:btih:{target_hash}",
                    }
                ]
            }
        )

        mock_response = MagicMock(status_code=200, text="OK")
        mock_instance.httpx_client.request = AsyncMock(return_value=mock_response)

        result = await pikpak_downloader.torrents_delete([target_hash], delete_files=True)

        assert result is True
        mock_instance.delete_to_trash.assert_awaited_once_with(ids=["folder_123"])

    @pytest.mark.asyncio
    async def test_torrents_delete_fallback_deletes_entire_save_path_for_sole_owner(
        self, pikpak_downloader, mock_pikpak_api, mock_database
    ):
        """Test delete_files can wipe the whole save_path when one hash owns it."""
        _, mock_instance = mock_pikpak_api
        _, mock_repo = mock_database
        target_hash = "abc123def456abc123def456abc123def456abc1"
        season_path = "downloads/Bangumi/Season 1"

        torrent_record = MagicMock()
        torrent_record.bangumi_id = 7
        torrent_record.hash = target_hash
        torrent_record.pikpak_cloud_path = season_path
        mock_repo.get_by_hash = AsyncMock(return_value=torrent_record)
        mock_repo.get_by_bangumi = AsyncMock(return_value=[torrent_record])

        mock_instance.offline_list = AsyncMock(
            return_value={
                "tasks": [
                    {
                        "id": "task_1",
                        "name": "Collection [01-12]",
                        "phase": "PHASE_TYPE_ERROR",
                        "file_url": f"magnet:?xt=urn:btih:{target_hash}",
                    }
                ]
            }
        )

        mock_response = MagicMock(status_code=200, text="OK")
        mock_instance.httpx_client.request = AsyncMock(return_value=mock_response)
        mock_instance.path_to_id = AsyncMock(
            side_effect=[
                [{"id": "season_id", "name": season_path}],
                [{"id": "season_id", "name": season_path}],
            ]
        )
        mock_instance.file_list = AsyncMock(return_value={"files": []})

        result = await pikpak_downloader.torrents_delete([target_hash], delete_files=True)

        assert result is True
        mock_instance.delete_to_trash.assert_awaited_once_with(ids=["season_id"])

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

    @pytest.mark.asyncio
    async def test_get_hash_status_map_treats_task_file_deleted_with_files_as_completed(
        self, pikpak_downloader, mock_pikpak_api
    ):
        """Hash status map should treat stale collection task as completed."""
        _, mock_instance = mock_pikpak_api
        target_hash = "abc123def456abc123def456abc123def456abc1"
        mock_instance.offline_list = AsyncMock(
            return_value={
                "tasks": [
                    {
                        "id": "task_1",
                        "name": "Collection [01-12]",
                        "file_name": "Collection [01-12]",
                        "phase": "PHASE_TYPE_ERROR",
                        "message": "File deleted",
                        "progress": 100,
                        "file_url": f"magnet:?xt=urn:btih:{target_hash}",
                        "params": {"error_detail": "task_file_deleted"},
                    }
                ]
            }
        )
        mock_instance.path_to_id = AsyncMock(
            return_value=[
                {"id": "dl_id", "name": "downloads"},
                {"id": "bg_id", "name": "Bangumi"},
                {"id": "season_id", "name": "Season 1"},
            ]
        )
        mock_instance.file_list = AsyncMock(
            return_value={
                "files": [
                    {"name": "Episode 01.mkv", "kind": "drive#file", "id": "e1"},
                ]
            }
        )

        result = await pikpak_downloader.get_hash_status_map()

        assert result[target_hash] == "completed"

    @pytest.mark.asyncio
    async def test_get_hash_status_map_single_file_deleted_does_not_use_other_episode_root_files(
        self, pikpak_downloader, mock_pikpak_api
    ):
        _, mock_instance = mock_pikpak_api
        target_hash = "abc123def456abc123def456abc123def456abc1"
        mock_instance.offline_list = AsyncMock(
            return_value={
                "tasks": [
                    {
                        "id": "task_1",
                        "name": "[LoliHouse] Nigetsuri - 04 [1080p].mkv",
                        "file_name": "[LoliHouse] Nigetsuri - 04 [1080p].mkv",
                        "phase": "PHASE_TYPE_ERROR",
                        "message": "File deleted",
                        "progress": 100,
                        "file_url": f"magnet:?xt=urn:btih:{target_hash}",
                        "params": {"error_detail": "task_file_deleted"},
                    }
                ]
            }
        )
        mock_instance.path_to_id = AsyncMock(
            return_value=[
                {"id": "dl_id", "name": "downloads"},
                {"id": "bg_id", "name": "Bangumi"},
            ]
        )
        mock_instance.file_list = AsyncMock(
            return_value={
                "files": [
                    {"name": "Nigetsuri S01E01.mkv", "kind": "drive#file", "id": "e1"},
                    {"name": "Nigetsuri S01E02.mkv", "kind": "drive#file", "id": "e2"},
                    {"name": "Nigetsuri S01E03.mkv", "kind": "drive#file", "id": "e3"},
                ]
            }
        )

        result = await pikpak_downloader.get_hash_status_map()

        assert result[target_hash] == "error"

    @pytest.mark.asyncio
    async def test_torrents_info_summarizes_untracked_tasks_without_warning_spam(
        self, pikpak_downloader, mock_pikpak_api, mock_database, caplog
    ):
        _, mock_instance = mock_pikpak_api
        _, mock_repo = mock_database

        tracked_hash = "abc123def456abc123def456abc123def456abc1"
        untracked_hash = "def456abc123def456abc123def456abc123def4"

        mock_instance.offline_list = AsyncMock(
            return_value={
                "tasks": [
                    {
                        "id": "task_tracked",
                        "name": "Tracked Show - 01",
                        "phase": "PHASE_TYPE_COMPLETE",
                        "progress": 100,
                        "file_url": f"magnet:?xt=urn:btih:{tracked_hash}",
                    },
                    {
                        "id": "task_untracked_1",
                        "name": "Untracked Show - 01",
                        "phase": "PHASE_TYPE_COMPLETE",
                        "progress": 100,
                        "file_url": f"magnet:?xt=urn:btih:{untracked_hash}",
                    },
                    {
                        "id": "task_untracked_2",
                        "name": "Untracked Show - 02",
                        "phase": "PHASE_TYPE_COMPLETE",
                        "progress": 100,
                        "file_url": f"magnet:?xt=urn:btih:{untracked_hash}",
                    },
                ]
            }
        )

        tracked_row = MagicMock()
        tracked_row.pikpak_cloud_path = "/downloads/Bangumi/Tracked Show/Season 1"
        mock_repo.get_by_hashes = AsyncMock(return_value={tracked_hash: tracked_row})

        with caplog.at_level(logging.WARNING):
            result = await pikpak_downloader.torrents_info(status_filter="all")

        assert len(result) == 1
        assert result[0].hash == tracked_hash
        assert "Skipping torrent Untracked Show - 01 - no cloud path in database" not in caplog.text
        assert "Skipping torrent Untracked Show - 02 - no cloud path in database" not in caplog.text


class TestCollectionTorrentDetection:
    MAGNET_HASH = "abc123def456abc123def456abc123def456abc1"
    MAGNET_URL = f"magnet:?xt=urn:btih:{MAGNET_HASH}"

    def _make_task(self, name: str, file_name: str = "", file_size: int = 0):
        return {
            "id": "task_1",
            "name": name,
            "phase": "PHASE_TYPE_COMPLETE",
            "progress": 100,
            "file_url": self.MAGNET_URL,
            "file_name": file_name,
            "file_size": file_size,
        }

    @pytest.mark.asyncio
    async def test_single_file_uses_task_file_name(
        self, pikpak_downloader, mock_pikpak_api
    ):
        _, mock_instance = mock_pikpak_api
        mock_instance.offline_list = AsyncMock(
            return_value={
                "tasks": [
                    self._make_task(
                        name="[Group] Episode 01.mkv",
                        file_name="[Group] Episode 01.mkv",
                        file_size=500_000_000,
                    )
                ]
            }
        )

        result = await pikpak_downloader.torrents_info(status_filter="completed")

        assert len(result) == 1
        assert len(result[0].files) == 1
        assert result[0].files[0].name == "[Group] Episode 01.mkv"
        assert result[0].files[0].size == 500_000_000
        mock_instance.file_list.assert_not_called()

    @pytest.mark.asyncio
    async def test_collection_folder_enumerates_files(
        self, pikpak_downloader, mock_pikpak_api
    ):
        _, mock_instance = mock_pikpak_api
        folder_name = "[DMG&LoliHouse] Re Zero [WebRip 1080p HEVC-10bit AAC ASSx2]"
        mock_instance.offline_list = AsyncMock(
            return_value={
                "tasks": [self._make_task(name=folder_name, file_name=folder_name)]
            }
        )

        async def path_to_id_side_effect(path, create=False):
            if folder_name in path:
                return [
                    {"id": "dl_id", "name": "downloads"},
                    {"id": "bg_id", "name": "Bangumi"},
                    {"id": "col_id", "name": folder_name},
                ]
            return [
                {"id": "dl_id", "name": "downloads"},
                {"id": "bg_id", "name": "Bangumi"},
            ]

        mock_instance.path_to_id = AsyncMock(side_effect=path_to_id_side_effect)

        async def file_list_side_effect(parent_id=None):
            if parent_id == "col_id":
                return {
                    "files": [
                        {"name": "episode01.mkv", "kind": "drive#file", "id": "e1"},
                        {"name": "episode02.mkv", "kind": "drive#file", "id": "e2"},
                        {"name": "subtitles.zip", "kind": "drive#file", "id": "s1"},
                    ]
                }
            if parent_id == "bg_id":
                return {
                    "files": [
                        {"name": folder_name, "kind": "drive#folder", "id": "col_id"},
                    ]
                }
            return {"files": []}

        mock_instance.file_list = AsyncMock(side_effect=file_list_side_effect)

        result = await pikpak_downloader.torrents_info(status_filter="completed")

        assert len(result) == 1
        files = result[0].files
        assert len(files) == 3
        assert files[0].name == f"{folder_name}/episode01.mkv"
        assert files[1].name == f"{folder_name}/episode02.mkv"
        assert files[2].name == f"{folder_name}/subtitles.zip"

    @pytest.mark.asyncio
    async def test_collection_folder_with_dotted_title_enumerates_files(
        self, pikpak_downloader, mock_pikpak_api
    ):
        _, mock_instance = mock_pikpak_api
        folder_name = (
            "[Sakurato][202601] Arisugawa Ren tte Honto wa Onna Nanda yo ne. "
            "[01-08 Fin][1080P][简繁内封]"
        )
        mock_instance.offline_list = AsyncMock(
            return_value={
                "tasks": [self._make_task(name=folder_name, file_name=folder_name)]
            }
        )

        async def path_to_id_side_effect(path, create=False):
            if folder_name in path:
                return [
                    {"id": "dl_id", "name": "downloads"},
                    {"id": "bg_id", "name": "Bangumi"},
                    {"id": "col_id", "name": folder_name},
                ]
            return [
                {"id": "dl_id", "name": "downloads"},
                {"id": "bg_id", "name": "Bangumi"},
            ]

        mock_instance.path_to_id = AsyncMock(side_effect=path_to_id_side_effect)

        async def file_list_side_effect(parent_id=None):
            if parent_id == "col_id":
                return {
                    "files": [
                        {"name": "episode01.mkv", "kind": "drive#file", "id": "e1"},
                        {"name": "episode02.mkv", "kind": "drive#file", "id": "e2"},
                    ]
                }
            if parent_id == "bg_id":
                return {
                    "files": [
                        {"name": folder_name, "kind": "drive#folder", "id": "col_id"},
                    ]
                }
            return {"files": []}

        mock_instance.file_list = AsyncMock(side_effect=file_list_side_effect)

        result = await pikpak_downloader.torrents_info(status_filter="completed")

        assert len(result) == 1
        assert [f.name for f in result[0].files] == [
            f"{folder_name}/episode01.mkv",
            f"{folder_name}/episode02.mkv",
        ]

    @pytest.mark.asyncio
    async def test_collection_empty_folder_marks_missing(
        self, pikpak_downloader, mock_pikpak_api
    ):
        _, mock_instance = mock_pikpak_api
        folder_name = "[Group] Collection [01-12]"
        mock_instance.offline_list = AsyncMock(
            return_value={
                "tasks": [self._make_task(name=folder_name, file_name=folder_name)]
            }
        )
        mock_instance.path_to_id = AsyncMock(return_value=None)

        result = await pikpak_downloader.torrents_info(status_filter="completed")

        assert len(result) == 1
        assert result[0].state == "missing"
        assert result[0].files == []

    @pytest.mark.asyncio
    async def test_no_file_name_falls_back_to_folder_listing(
        self, pikpak_downloader, mock_pikpak_api
    ):
        _, mock_instance = mock_pikpak_api
        mock_instance.offline_list = AsyncMock(
            return_value={
                "tasks": [self._make_task(name="Some Task", file_name="")]
            }
        )
        mock_instance.path_to_id = AsyncMock(
            return_value=[
                {"id": "dl_id", "name": "downloads"},
                {"id": "bg_id", "name": "Bangumi"},
            ]
        )
        mock_instance.file_list = AsyncMock(
            return_value={
                "files": [
                    {"name": "file.mkv", "kind": "drive#file", "id": "f1"},
                ]
            }
        )

        result = await pikpak_downloader.torrents_info(status_filter="completed")

        assert len(result) == 1
        assert len(result[0].files) == 1
        assert result[0].files[0].name == "file.mkv"


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


class TestPikPakRenameFile:
    @pytest.mark.asyncio
    async def test_rename_file_falls_back_to_parent_exact_name_lookup(
        self, pikpak_downloader, mock_pikpak_api
    ):
        _, mock_instance = mock_pikpak_api

        old_name = "[Studio GreenTea] Kirei ni Shite Moraemasu ka [01].mp4"
        new_name = "能帮我弄干净吗？ S01E01.mp4"

        async def path_to_id_side_effect(path, create=False):
            if path == "/downloads/Bangumi":
                return [{"id": "folder_id", "name": "downloads/Bangumi"}]
            if path in {
                f"/downloads/Bangumi/{old_name}",
                f"/downloads/Bangumi/{new_name}",
            }:
                return [{"id": "folder_id", "name": "downloads/Bangumi"}]
            return None

        mock_instance.path_to_id = AsyncMock(side_effect=path_to_id_side_effect)
        mock_instance.file_list = AsyncMock(
            return_value={
                "files": [
                    {
                        "id": "file_id",
                        "name": old_name,
                        "kind": "drive#file",
                    }
                ]
            }
        )
        mock_instance.file_rename = AsyncMock(return_value={"id": "file_id"})

        result = await pikpak_downloader.torrents_rename_file(
            "abc123def456abc123def456abc123def456abc1",
            old_name,
            new_name,
        )

        assert result is True
        mock_instance.file_rename.assert_awaited_once_with(
            id="file_id",
            new_file_name=new_name,
        )

    @pytest.mark.asyncio
    async def test_rename_file_skips_partial_resolution_warning_when_target_exists(
        self, pikpak_downloader, mock_pikpak_api, caplog
    ):
        _, mock_instance = mock_pikpak_api

        old_name = "[LoliHouse] Isekai Nonbiri Nouka 2 - 02 [WebRip 1080p HEVC-10bit AAC SRTx2].mkv"
        new_name = "异世界悠闲农家 第二季 S02E02.mkv"

        async def path_to_id_side_effect(path, create=False):
            if path == "/downloads/Bangumi":
                return [{"id": "folder_id", "name": "downloads/Bangumi"}]
            if path in {
                f"/downloads/Bangumi/{old_name}",
                f"/downloads/Bangumi/{new_name}",
            }:
                return [{"id": "folder_id", "name": "downloads/Bangumi"}]
            return None

        mock_instance.path_to_id = AsyncMock(side_effect=path_to_id_side_effect)
        mock_instance.file_list = AsyncMock(
            return_value={
                "files": [
                    {
                        "id": "target_file_id",
                        "name": new_name,
                        "kind": "drive#file",
                    }
                ]
            }
        )
        mock_instance.file_rename = AsyncMock()

        with caplog.at_level(logging.WARNING):
            result = await pikpak_downloader.torrents_rename_file(
                "abc123def456abc123def456abc123def456abc1",
                old_name,
                new_name,
            )

        assert result is True
        assert "Partial path resolution in _find_file_id_by_path" not in caplog.text
        assert "File not found for rename" not in caplog.text
        mock_instance.file_rename.assert_not_awaited()


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


class TestLoginCooldown:

    @pytest.mark.asyncio
    async def test_login_failure_sets_cooldown(
        self, pikpak_downloader, mock_pikpak_api
    ):
        _, mock_instance = mock_pikpak_api
        mock_instance.refresh_token = None
        mock_instance.login = AsyncMock(side_effect=Exception("too frequent"))
        pikpak_downloader._client.refresh_token = None
        pikpak_downloader._token_expires_at = 0

        with pytest.raises(Exception, match="too frequent"):
            await pikpak_downloader._ensure_valid_token()

        assert pikpak_downloader._login_cooldown_until > 0

    @pytest.mark.asyncio
    async def test_cooldown_blocks_subsequent_login(
        self, pikpak_downloader, mock_pikpak_api
    ):
        import time

        _, mock_instance = mock_pikpak_api
        pikpak_downloader._token_expires_at = 0
        pikpak_downloader._client.refresh_token = None
        pikpak_downloader._login_cooldown_until = time.time() + 9999

        with pytest.raises(RuntimeError, match="cooldown"):
            await pikpak_downloader._ensure_valid_token()

        mock_instance.login.assert_not_called()

    @pytest.mark.asyncio
    async def test_successful_login_clears_cooldown(
        self, pikpak_downloader, mock_pikpak_api
    ):
        import time

        _, mock_instance = mock_pikpak_api
        pikpak_downloader._token_expires_at = 0
        pikpak_downloader._client.refresh_token = None
        pikpak_downloader._login_cooldown_until = time.time() - 1

        await pikpak_downloader._ensure_valid_token()

        mock_instance.login.assert_called_once()
        assert pikpak_downloader._login_cooldown_until == 0

    @pytest.mark.asyncio
    async def test_refresh_failure_falls_through_to_login(
        self, pikpak_downloader, mock_pikpak_api
    ):
        _, mock_instance = mock_pikpak_api
        pikpak_downloader._token_expires_at = 0
        pikpak_downloader._client.refresh_token = "some_token"
        mock_instance.refresh_access_token = AsyncMock(
            side_effect=Exception("refresh failed")
        )

        await pikpak_downloader._ensure_valid_token()

        mock_instance.refresh_access_token.assert_called_once()
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


class TestInvalidatePathCache:
    @pytest.mark.asyncio
    async def test_invalidate_path_cache_clears_cache(self, pikpak_downloader):
        pikpak_downloader._client._path_id_cache = {"/some/path": {"id": "old_id"}}
        pikpak_downloader._invalidate_path_cache()
        assert pikpak_downloader._client._path_id_cache == {}

    @pytest.mark.asyncio
    async def test_invalidate_path_cache_handles_missing_attribute(
        self, pikpak_downloader
    ):
        if hasattr(pikpak_downloader._client, "_path_id_cache"):
            delattr(pikpak_downloader._client, "_path_id_cache")
        pikpak_downloader._invalidate_path_cache()

    @pytest.mark.asyncio
    async def test_torrents_info_calls_invalidate_path_cache(
        self, pikpak_downloader, mock_pikpak_api
    ):
        _, mock_instance = mock_pikpak_api
        mock_instance.offline_list = AsyncMock(return_value={"tasks": []})

        with patch.object(
            pikpak_downloader, "_invalidate_path_cache"
        ) as mock_invalidate:
            await pikpak_downloader.torrents_info()
            mock_invalidate.assert_called_once()


class TestCollectionRetriggerRootFiles:
    MAGNET_HASH = "abc123def456abc123def456abc123def456abc1"
    MAGNET_URL = f"magnet:?xt=urn:btih:{MAGNET_HASH}"
    FOLDER_NAME = "[DMG&LoliHouse] Re Zero [1080p]"

    def _make_task(self):
        return {
            "id": "task_1",
            "name": self.FOLDER_NAME,
            "phase": "PHASE_TYPE_COMPLETE",
            "progress": 100,
            "file_url": self.MAGNET_URL,
            "file_name": self.FOLDER_NAME,
            "file_size": 0,
        }

    @pytest.mark.asyncio
    async def test_retrigger_finds_files_moved_to_root(
        self, pikpak_downloader, mock_pikpak_api
    ):
        """After first rename moves media from collection subfolder to save_path
        root, retrigger should still find those files via root scan."""
        _, mock_instance = mock_pikpak_api
        mock_instance.offline_list = AsyncMock(
            return_value={"tasks": [self._make_task()]}
        )

        call_count = 0

        async def path_to_id_side_effect(path, create=False):
            nonlocal call_count
            call_count += 1
            if self.FOLDER_NAME in path:
                return [
                    {"id": "dl_id", "name": "downloads"},
                    {"id": "bg_id", "name": "Bangumi"},
                    {"id": "col_id", "name": self.FOLDER_NAME},
                ]
            return [
                {"id": "dl_id", "name": "downloads"},
                {"id": "bg_id", "name": "Bangumi"},
            ]

        mock_instance.path_to_id = AsyncMock(side_effect=path_to_id_side_effect)

        file_list_call_count = 0

        async def file_list_side_effect(parent_id=None):
            nonlocal file_list_call_count
            file_list_call_count += 1
            if parent_id == "col_id":
                return {"files": [
                    {"name": "subtitles.zip", "kind": "drive#file", "id": "s1"},
                ]}
            if parent_id == "bg_id":
                return {"files": [
                    {"name": "Re Zero S02E01.mkv", "kind": "drive#file", "id": "m1"},
                    {"name": "Re Zero S02E02.mkv", "kind": "drive#file", "id": "m2"},
                    {"name": self.FOLDER_NAME, "kind": "drive#folder", "id": "col_id"},
                ]}
            return {"files": []}

        mock_instance.file_list = AsyncMock(side_effect=file_list_side_effect)

        result = await pikpak_downloader.torrents_info(status_filter="completed")

        assert len(result) == 1
        files = result[0].files
        file_names = [f.name for f in files]
        assert f"{self.FOLDER_NAME}/subtitles.zip" in file_names
        assert "Re Zero S02E01.mkv" in file_names
        assert "Re Zero S02E02.mkv" in file_names
        assert len(files) == 3

    @pytest.mark.asyncio
    async def test_root_files_excluded_by_collection_prefix_match(
        self, pikpak_downloader, mock_pikpak_api
    ):
        """Root files whose name matches a collection-prefixed name are still
        included because they have different relative paths — this is correct
        since they represent different physical locations."""
        _, mock_instance = mock_pikpak_api
        mock_instance.offline_list = AsyncMock(
            return_value={"tasks": [self._make_task()]}
        )

        async def path_to_id_side_effect(path, create=False):
            if self.FOLDER_NAME in path:
                return [
                    {"id": "dl_id", "name": "downloads"},
                    {"id": "bg_id", "name": "Bangumi"},
                    {"id": "col_id", "name": self.FOLDER_NAME},
                ]
            return [
                {"id": "dl_id", "name": "downloads"},
                {"id": "bg_id", "name": "Bangumi"},
            ]

        mock_instance.path_to_id = AsyncMock(side_effect=path_to_id_side_effect)

        async def file_list_side_effect(parent_id=None):
            if parent_id == "col_id":
                return {"files": [
                    {"name": "episode01.mkv", "kind": "drive#file", "id": "e1"},
                ]}
            if parent_id == "bg_id":
                return {"files": [
                    {"name": "episode01.mkv", "kind": "drive#file", "id": "e1_root"},
                    {"name": self.FOLDER_NAME, "kind": "drive#folder", "id": "col_id"},
                ]}
            return {"files": []}

        mock_instance.file_list = AsyncMock(side_effect=file_list_side_effect)

        result = await pikpak_downloader.torrents_info(status_filter="completed")

        files = result[0].files
        names = [f.name for f in files]
        assert f"{self.FOLDER_NAME}/episode01.mkv" in names
        assert "episode01.mkv" in names
        assert len(files) == 2

    @pytest.mark.asyncio
    async def test_first_rename_no_root_files_still_works(
        self, pikpak_downloader, mock_pikpak_api
    ):
        """On first rename (no files moved yet), root scan finds nothing extra
        and collection subfolder files are returned normally."""
        _, mock_instance = mock_pikpak_api
        mock_instance.offline_list = AsyncMock(
            return_value={"tasks": [self._make_task()]}
        )

        async def path_to_id_side_effect(path, create=False):
            if self.FOLDER_NAME in path:
                return [
                    {"id": "dl_id", "name": "downloads"},
                    {"id": "bg_id", "name": "Bangumi"},
                    {"id": "col_id", "name": self.FOLDER_NAME},
                ]
            return [
                {"id": "dl_id", "name": "downloads"},
                {"id": "bg_id", "name": "Bangumi"},
            ]

        mock_instance.path_to_id = AsyncMock(side_effect=path_to_id_side_effect)

        async def file_list_side_effect(parent_id=None):
            if parent_id == "col_id":
                return {"files": [
                    {"name": "ep01.mkv", "kind": "drive#file", "id": "e1"},
                    {"name": "ep02.mkv", "kind": "drive#file", "id": "e2"},
                ]}
            if parent_id == "bg_id":
                return {"files": [
                    {
                        "name": self.FOLDER_NAME,
                        "kind": "drive#folder",
                        "id": "col_id",
                    },
                ]}
            return {"files": []}

        mock_instance.file_list = AsyncMock(side_effect=file_list_side_effect)

        result = await pikpak_downloader.torrents_info(status_filter="completed")

        files = result[0].files
        assert len(files) == 2
        assert files[0].name == f"{self.FOLDER_NAME}/ep01.mkv"
        assert files[1].name == f"{self.FOLDER_NAME}/ep02.mkv"


class TestListDirectFilesInFolder:

    @pytest.mark.asyncio
    async def test_returns_only_files_not_folders(
        self, pikpak_downloader, mock_pikpak_api
    ):
        _, mock_instance = mock_pikpak_api
        mock_instance.path_to_id = AsyncMock(
            return_value=[{"id": "root_id", "name": "Season 2"}]
        )
        mock_instance.file_list = AsyncMock(
            return_value={
                "files": [
                    {"name": "ep01.mkv", "kind": "drive#file", "id": "f1"},
                    {"name": "Subfolder", "kind": "drive#folder", "id": "d1"},
                    {"name": "ep02.mkv", "kind": "drive#file", "id": "f2"},
                ]
            }
        )

        files = await pikpak_downloader._list_direct_files_in_folder("/Season 2")

        assert len(files) == 2
        assert files[0].name == "ep01.mkv"
        assert files[1].name == "ep02.mkv"

    @pytest.mark.asyncio
    async def test_returns_empty_for_missing_folder(
        self, pikpak_downloader, mock_pikpak_api
    ):
        _, mock_instance = mock_pikpak_api
        mock_instance.path_to_id = AsyncMock(return_value=None)

        files = await pikpak_downloader._list_direct_files_in_folder("/nonexistent")

        assert files == []

    @pytest.mark.asyncio
    async def test_handles_api_error_gracefully(
        self, pikpak_downloader, mock_pikpak_api
    ):
        _, mock_instance = mock_pikpak_api
        mock_instance.path_to_id = AsyncMock(side_effect=Exception("API error"))

        files = await pikpak_downloader._list_direct_files_in_folder("/broken")

        assert files == []
