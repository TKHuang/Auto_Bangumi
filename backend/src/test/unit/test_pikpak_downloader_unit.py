"""Unit tests for PikPak downloader client.

Tests the PikPakDownloader class methods with mocked PikPakApi calls,
ensuring proper async/sync bridging, error handling, and API compatibility.
"""

import json
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# --- Fixtures ---


@pytest.fixture
def mock_pikpak_api():
    """Create a mock PikPakApi instance.

    Returns tuple of (MockClass, mock_instance) for configuring test behavior.
    """
    with patch("module.downloader.client.pikpak_downloader.PikPakApi") as MockApi:
        mock_instance = MagicMock()

        # Configure async methods
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

        # Configure synchronous attributes
        mock_instance.access_token = "test_access_token"
        mock_instance.refresh_token = "test_refresh_token"
        mock_instance.user_id = "test_user_123"
        mock_instance.encode_token = MagicMock()

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
    with patch("module.downloader.client.pikpak_downloader.Database") as MockDatabase:
        mock_db_instance = MagicMock()
        mock_torrent_db = MagicMock()
        # Default mock torrent with cloud path set (for tests that use torrents_info)
        default_torrent = MagicMock()
        default_torrent.pikpak_cloud_path = "/downloads/Bangumi"
        default_torrent.renamed_at = None
        mock_torrent_db.search_by_hash = MagicMock(return_value=default_torrent)
        mock_db_instance.torrent = mock_torrent_db
        MockDatabase.return_value.__enter__ = MagicMock(return_value=mock_db_instance)
        MockDatabase.return_value.__exit__ = MagicMock(return_value=False)
        yield MockDatabase, mock_db_instance


@pytest.fixture
def pikpak_downloader(mock_pikpak_api, mock_database, temp_config_dir):
    """Create a PikPakDownloader instance with mocked dependencies."""
    MockApi, mock_instance = mock_pikpak_api

    # Patch file paths to use temp directory
    with (
        patch(
            "module.downloader.client.pikpak_downloader.TOKEN_FILE",
            os.path.join(temp_config_dir, "pikpak_token.json"),
        ),
        patch(
            "module.downloader.client.pikpak_downloader.HASH_MAP_FILE",
            os.path.join(temp_config_dir, "pikpak_hash_map.json"),
        ),
    ):
        from module.downloader.client.pikpak_downloader import PikPakDownloader

        downloader = PikPakDownloader("test@example.com", "password123")
        yield downloader


@pytest.fixture
def pikpak_downloader_with_token(mock_pikpak_api, mock_database, temp_config_dir):
    """Create a PikPakDownloader with pre-existing valid token."""
    MockApi, mock_instance = mock_pikpak_api

    token_file = os.path.join(temp_config_dir, "pikpak_token.json")
    hash_map_file = os.path.join(temp_config_dir, "pikpak_hash_map.json")

    # Write valid token file (expires in future)
    import time

    token_data = {
        "access_token": "existing_access_token",
        "refresh_token": "existing_refresh_token",
        "user_id": "existing_user_123",
        "expires_at": int(time.time()) + 7200,  # Valid for 2 hours
    }
    os.makedirs(temp_config_dir, exist_ok=True)
    with open(token_file, "w") as f:
        json.dump(token_data, f)

    # Write hash map file
    hash_map_data = {"abc123def456": "/AutoBangumi/Test Series/Season 1"}
    with open(hash_map_file, "w") as f:
        json.dump(hash_map_data, f)

    with (
        patch("module.downloader.client.pikpak_downloader.TOKEN_FILE", token_file),
        patch(
            "module.downloader.client.pikpak_downloader.HASH_MAP_FILE", hash_map_file
        ),
    ):
        from module.downloader.client.pikpak_downloader import PikPakDownloader

        downloader = PikPakDownloader("test@example.com", "password123")
        yield downloader


# --- Test Classes ---


@pytest.mark.unit
class TestPikPakDownloaderInit:
    """Tests for PikPakDownloader initialization."""

    def test_init_without_token(self, pikpak_downloader, mock_pikpak_api):
        """Test initialization without existing token file."""
        _, mock_instance = mock_pikpak_api

        assert pikpak_downloader._username == "test@example.com"
        assert pikpak_downloader._client == mock_instance
        assert pikpak_downloader._hash_map == {}
        assert pikpak_downloader._token_expires_at == 0

    def test_init_with_valid_token(self, pikpak_downloader_with_token, mock_pikpak_api):
        """Test initialization loads existing valid token."""
        _, mock_instance = mock_pikpak_api

        # Token should have been loaded
        assert mock_instance.access_token == "existing_access_token"
        assert mock_instance.refresh_token == "existing_refresh_token"
        assert mock_instance.user_id == "existing_user_123"
        assert mock_instance.encode_token.called

        # Hash map should have been loaded
        assert "abc123def456" in pikpak_downloader_with_token._hash_map

    def test_init_with_expired_token(self, mock_pikpak_api, temp_config_dir):
        """Test initialization loads expired token (refresh_token may still be valid)."""
        MockApi, mock_instance = mock_pikpak_api

        token_file = os.path.join(temp_config_dir, "pikpak_token.json")

        # Write expired token
        import time

        token_data = {
            "access_token": "expired_token",
            "refresh_token": "expired_refresh",
            "user_id": "user_123",
            "expires_at": int(time.time()) - 100,  # Already expired
        }
        os.makedirs(temp_config_dir, exist_ok=True)
        with open(token_file, "w") as f:
            json.dump(token_data, f)

        with (
            patch("module.downloader.client.pikpak_downloader.TOKEN_FILE", token_file),
            patch(
                "module.downloader.client.pikpak_downloader.HASH_MAP_FILE",
                os.path.join(temp_config_dir, "hash_map.json"),
            ),
        ):
            from module.downloader.client.pikpak_downloader import PikPakDownloader

            downloader = PikPakDownloader("test@example.com", "password123")

            # Token expires_at should be 0 (forcing refresh on first use)
            # but tokens ARE loaded (refresh_token may still work)
            assert downloader._token_expires_at == 0
            # encode_token is called because we load the tokens for potential refresh
            assert mock_instance.encode_token.called


@pytest.mark.unit
class TestPikPakDownloaderAuth:
    """Tests for PikPakDownloader authentication."""

    def test_auth_success(self, pikpak_downloader, mock_pikpak_api):
        """Test successful authentication."""
        _, mock_instance = mock_pikpak_api

        result = pikpak_downloader.auth()

        assert result is True
        mock_instance.login.assert_called_once()
        assert pikpak_downloader._token_expires_at > 0

    def test_auth_failure_propagates_exception(
        self, pikpak_downloader, mock_pikpak_api
    ):
        """Test authentication failure raises exception."""
        _, mock_instance = mock_pikpak_api
        mock_instance.login = AsyncMock(side_effect=Exception("Invalid credentials"))

        with pytest.raises(Exception, match="Invalid credentials"):
            pikpak_downloader.auth()

    def test_check_host_success(self, pikpak_downloader):
        """Test check_host returns True when API is reachable."""
        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            result = pikpak_downloader.check_host()

            assert result is True
            mock_get.assert_called_once()

    def test_check_host_failure(self, pikpak_downloader):
        """Test check_host returns False when API is unreachable."""
        with patch("requests.get") as mock_get:
            import requests

            mock_get.side_effect = requests.exceptions.ConnectionError()

            result = pikpak_downloader.check_host()

            assert result is False

    def test_logout_is_noop(self, pikpak_downloader):
        """Test logout does nothing (preserves tokens)."""
        pikpak_downloader._token_expires_at = 12345

        pikpak_downloader.logout()

        # Token should still be set (not deleted)
        assert pikpak_downloader._token_expires_at == 12345


@pytest.mark.unit
class TestPikPakDownloaderTorrents:
    """Tests for torrent operations."""

    def test_add_torrents_single_url(
        self, pikpak_downloader, mock_pikpak_api, mock_database
    ):
        """Test adding a single magnet URL."""
        _, mock_instance = mock_pikpak_api

        result = pikpak_downloader.add_torrents(
            torrent_urls="magnet:?xt=urn:btih:abc123def456abc123def456abc123def456abc1&dn=test",
            save_path="Test Series/Season 1",
        )

        assert result is True
        mock_instance.offline_download.assert_called_once()

    def test_add_torrents_multiple_urls(self, pikpak_downloader, mock_pikpak_api):
        """Test adding multiple magnet URLs."""
        _, mock_instance = mock_pikpak_api

        urls = [
            "magnet:?xt=urn:btih:1111111111111111111111111111111111111111&dn=ep1",
            "magnet:?xt=urn:btih:2222222222222222222222222222222222222222&dn=ep2",
        ]

        result = pikpak_downloader.add_torrents(
            torrent_urls=urls, save_path="Test Series/Season 1"
        )

        assert result is True
        assert mock_instance.offline_download.call_count == 2

    def test_add_torrents_no_urls_returns_false(self, pikpak_downloader):
        """Test add_torrents returns False when no URLs provided."""
        result = pikpak_downloader.add_torrents(torrent_urls=None)
        assert result is False

    def test_add_torrents_torrent_files_not_supported(
        self, pikpak_downloader, mock_pikpak_api
    ):
        """Test that torrent files are rejected."""
        result = pikpak_downloader.add_torrents(
            torrent_urls=None, torrent_files=b"fake torrent content"
        )
        assert result is False

    def test_torrents_info_completed(self, pikpak_downloader, mock_pikpak_api):
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
        # Mock file_list to return files so state stays "completed" (not "missing")
        mock_instance.file_list = AsyncMock(
            return_value={
                "files": [
                    {"name": "Test Episode 01.mkv", "kind": "drive#file"}
                ]
            }
        )

        result = pikpak_downloader.torrents_info(status_filter="completed")

        assert len(result) == 1
        assert result[0].name == "Test Episode 01.mkv"
        assert result[0].state == "completed"
        assert result[0].progress == 1.0

    def test_torrents_info_downloading(self, pikpak_downloader, mock_pikpak_api):
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

        result = pikpak_downloader.torrents_info(status_filter="downloading")

        assert len(result) == 1
        assert result[0].state == "downloading"
        assert result[0].progress == 0.5

    def test_torrents_delete_single_hash(self, pikpak_downloader, mock_pikpak_api):
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

        pikpak_downloader._hash_map["abc123def456abc123def456abc123def456abc1"] = (
            "/path"
        )
        pikpak_downloader.torrents_delete("abc123def456abc123def456abc123def456abc1")

        mock_instance.delete_tasks.assert_called_once()

    def test_torrents_delete_multiple_hashes(self, pikpak_downloader, mock_pikpak_api):
        """Test deleting multiple torrents."""
        _, mock_instance = mock_pikpak_api
        mock_instance.offline_list = AsyncMock(return_value={"tasks": []})

        hashes = [
            "1111111111111111111111111111111111111111",
            "2222222222222222222222222222222222222222",
        ]

        pikpak_downloader.torrents_delete(hashes)

        # Should have called offline_list multiple times (at least once per hash)
        # May call more times due to internal torrents_info() calls
        assert mock_instance.offline_list.call_count >= 2

    def test_get_existing_hashes(self, pikpak_downloader, mock_pikpak_api):
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

        result = pikpak_downloader.get_existing_hashes()

        assert len(result) == 2
        assert "abc123def456abc123def456abc123def456abc1" in result
        assert "def456abc123def456abc123def456abc12345ef" in result


@pytest.mark.unit
class TestPikPakDownloaderStubs:
    """Tests for stub methods required for API compatibility."""

    def test_get_app_prefs(self, pikpak_downloader):
        """Test get_app_prefs returns configured downloader path."""
        from module.conf import settings

        result = pikpak_downloader.get_app_prefs()

        assert "save_path" in result
        assert result["save_path"] == settings.downloader.path

    def test_prefs_init_is_noop(self, pikpak_downloader):
        """Test prefs_init does nothing but doesn't error."""
        # Should not raise
        pikpak_downloader.prefs_init({"some": "prefs"})

    def test_add_category_is_noop(self, pikpak_downloader):
        """Test add_category does nothing but doesn't error."""
        pikpak_downloader.add_category("BangumiCollection")

    def test_rss_add_feed_is_noop(self, pikpak_downloader):
        """Test RSS methods are no-ops."""
        pikpak_downloader.rss_add_feed("http://example.com/rss", "Mikan_RSS")

    def test_rss_get_feeds_returns_empty(self, pikpak_downloader):
        """Test RSS feed retrieval returns empty dict."""
        result = pikpak_downloader.rss_get_feeds()
        assert result == {}


@pytest.mark.unit
class TestPikPakDownloaderHashExtraction:
    """Tests for torrent hash extraction from magnet links."""

    def test_extract_hash_from_magnet(self, pikpak_downloader):
        """Test extracting hash from standard magnet link."""
        url = "magnet:?xt=urn:btih:abc123def456abc123def456abc123def456abc1&dn=test"
        result = pikpak_downloader._extract_hash(url)
        assert result == "abc123def456abc123def456abc123def456abc1"

    def test_extract_hash_case_insensitive(self, pikpak_downloader):
        """Test hash extraction is case insensitive."""
        url = "magnet:?xt=URN:BTIH:ABC123DEF456ABC123DEF456ABC123DEF456ABC1&dn=test"
        result = pikpak_downloader._extract_hash(url)
        assert result.lower() == "abc123def456abc123def456abc123def456abc1"

    def test_extract_hash_no_match(self, pikpak_downloader):
        """Test hash extraction returns None for invalid URLs."""
        result = pikpak_downloader._extract_hash("https://example.com/not-a-magnet")
        assert result is None


@pytest.mark.unit
class TestPikPakDownloaderTokenRefresh:
    """Tests for token refresh mechanism."""

    def test_ensure_valid_token_valid(
        self, pikpak_downloader_with_token, mock_pikpak_api
    ):
        """Test _ensure_valid_token does nothing when token is valid."""
        _, mock_instance = mock_pikpak_api

        # Token is valid (set in fixture)
        pikpak_downloader_with_token._ensure_valid_token()

        # Should not have tried to refresh
        mock_instance.refresh_access_token.assert_not_called()
        mock_instance.login.assert_not_called()

    def test_ensure_valid_token_expires_soon(self, pikpak_downloader, mock_pikpak_api):
        """Test _ensure_valid_token refreshes when token expires soon."""
        _, mock_instance = mock_pikpak_api
        import time

        # Set token to expire in 2 minutes (within 5-minute threshold)
        pikpak_downloader._token_expires_at = int(time.time()) + 120
        pikpak_downloader._client.refresh_token = "test_refresh"

        pikpak_downloader._ensure_valid_token()

        mock_instance.refresh_access_token.assert_called_once()

    def test_ensure_valid_token_no_refresh_token(
        self, pikpak_downloader, mock_pikpak_api
    ):
        """Test _ensure_valid_token re-authenticates when no refresh token."""
        _, mock_instance = mock_pikpak_api
        import time

        # Set expired token with no refresh token
        pikpak_downloader._token_expires_at = int(time.time()) - 100
        pikpak_downloader._client.refresh_token = None

        pikpak_downloader._ensure_valid_token()

        mock_instance.login.assert_called_once()


@pytest.mark.unit
class TestPikPakDownloaderThreadSafety:
    """Tests for thread safety mechanisms."""

    def test_run_async_uses_lock(self, pikpak_downloader, mock_pikpak_api):
        """Test that _run_async acquires lock before executing."""
        _, mock_instance = mock_pikpak_api

        # The lock should be released after the call
        pikpak_downloader._run_async(mock_instance.login())

        # If we can acquire the lock, it was released
        assert pikpak_downloader._lock.acquire(blocking=False)
        pikpak_downloader._lock.release()


@pytest.mark.unit
class TestPikPakDownloaderHashMapPersistence:
    """Tests for hash map persistence."""

    def test_hash_map_loaded_on_init(self, pikpak_downloader_with_token):
        """Test hash map is loaded from file on initialization."""
        assert "abc123def456" in pikpak_downloader_with_token._hash_map
        assert (
            pikpak_downloader_with_token._hash_map["abc123def456"]
            == "/AutoBangumi/Test Series/Season 1"
        )

    def test_database_updated_after_add(
        self, pikpak_downloader, mock_pikpak_api, mock_database
    ):
        """Test database is updated after adding torrent."""
        _, mock_instance = mock_pikpak_api
        MockDatabase, mock_db_instance = mock_database

        # Create a mock torrent record that will be updated
        mock_torrent = MagicMock()
        mock_torrent.name = "Test Torrent"
        mock_db_instance.torrent.search_by_hash.return_value = mock_torrent

        pikpak_downloader.add_torrents(
            torrent_urls="magnet:?xt=urn:btih:abc123def456abc123def456abc123def456abc1",
            save_path="Test",
        )

        # Verify database update was called
        mock_db_instance.torrent.update.assert_called()
        # Verify cloud path was set on the torrent
        assert mock_torrent.pikpak_cloud_path == "Test"


@pytest.mark.unit
class TestTorrentInfoDataclass:
    """Tests for TorrentInfo and TorrentFile dataclasses."""

    def test_torrent_info_with_files(self, pikpak_downloader):
        """Test TorrentInfo includes files list."""
        from module.downloader.client.pikpak_downloader import TorrentFile, TorrentInfo

        files = [
            TorrentFile(name="Episode 01.mkv"),
            TorrentFile(name="Episode 02.mkv"),
        ]
        info = TorrentInfo(
            hash="abc123",
            name="Test Series",
            state="completed",
            progress=1.0,
            save_path="/path",
            files=files,
        )

        assert len(info.files) == 2
        assert info.files[0].name == "Episode 01.mkv"

    def test_torrent_info_default_files(self, pikpak_downloader):
        """Test TorrentInfo defaults to empty files list."""
        from module.downloader.client.pikpak_downloader import TorrentInfo

        info = TorrentInfo(
            hash="abc123",
            name="Test",
            state="completed",
            progress=1.0,
            save_path="/path",
        )

        assert info.files == []


@pytest.mark.unit
class TestPikPakDownloaderClassAttributes:
    """Tests for class-level attributes."""

    def test_supports_torrent_files_is_false(self):
        """Test that supports_torrent_files is False for PikPak."""
        from module.downloader.client.pikpak_downloader import PikPakDownloader

        assert PikPakDownloader.supports_torrent_files is False


# --- Edge Case Tests (Phase 3) ---


@pytest.mark.unit
class TestPikPakMoveMultiFileTorrent:
    """Tests for multi-file torrent move operations."""

    def test_move_torrent_moves_folder_directly(
        self, pikpak_downloader, mock_pikpak_api
    ):
        """Test that move_torrent moves a folder directly (efficient behavior)."""
        _, mock_instance = mock_pikpak_api

        # Setup hash map with existing torrent
        test_hash = "abc123def456abc123def456abc123def456abc1"
        pikpak_downloader._hash_map[test_hash] = "/AutoBangumi/Old/Path"

        # Mock offline_list to return matching torrent
        mock_instance.offline_list = AsyncMock(
            return_value={
                "tasks": [
                    {
                        "id": "task_1",
                        "name": "Multi-File-Torrent",
                        "phase": "PHASE_TYPE_COMPLETE",
                        "progress": 100,
                        "file_url": f"magnet:?xt=urn:btih:{test_hash}",
                    }
                ]
            }
        )

        # Mock path_to_id to return folder info
        mock_instance.path_to_id = AsyncMock(
            return_value=[{"id": "folder_123", "name": "folder"}]
        )

        # Mock file_list to return the torrent folder so _find_file_or_folder_id_by_name works
        mock_instance.file_list = AsyncMock(
            return_value={
                "files": [
                    {"id": "torrent_folder_id", "name": "Multi-File-Torrent", "kind": "drive#folder"}
                ]
            }
        )

        # Mock file_batch_move
        mock_instance.file_batch_move = AsyncMock(return_value={"task_id": "move_123"})

        result = pikpak_downloader.move_torrent([test_hash], "New/Path")

        assert result is True
        # Verify file_batch_move was called with the folder ID
        mock_instance.file_batch_move.assert_called_once()
        call_args = mock_instance.file_batch_move.call_args
        moved_ids = call_args.kwargs.get("ids", call_args[1].get("ids", []))
        # Moving folder directly is correct - contains all files
        assert len(moved_ids) == 1
        assert "torrent_folder_id" in moved_ids

    def test_move_multiple_torrents(self, pikpak_downloader, mock_pikpak_api):
        """Test moving multiple torrents in one call."""
        _, mock_instance = mock_pikpak_api

        hash1 = "1111111111111111111111111111111111111111"
        hash2 = "2222222222222222222222222222222222222222"
        pikpak_downloader._hash_map[hash1] = "/AutoBangumi/Old1"
        pikpak_downloader._hash_map[hash2] = "/AutoBangumi/Old2"

        # Mock offline_list to return both torrents
        mock_instance.offline_list = AsyncMock(
            return_value={
                "tasks": [
                    {
                        "id": "task_1",
                        "name": "Torrent1",
                        "phase": "PHASE_TYPE_COMPLETE",
                        "file_url": f"magnet:?xt=urn:btih:{hash1}",
                    },
                    {
                        "id": "task_2",
                        "name": "Torrent2",
                        "phase": "PHASE_TYPE_COMPLETE",
                        "file_url": f"magnet:?xt=urn:btih:{hash2}",
                    },
                ]
            }
        )

        folder_call_count = [0]

        def path_to_id_side_effect(path, create=False):
            folder_call_count[0] += 1
            return [{"id": f"folder_{folder_call_count[0]}", "name": "folder"}]

        mock_instance.path_to_id = AsyncMock(side_effect=path_to_id_side_effect)

        # Track which folder is being listed to return correct files
        file_list_call_count = [0]

        def file_list_side_effect(parent_id=None):
            file_list_call_count[0] += 1
            # Return different files based on call order
            # First calls are for torrents_info file checking, then for move lookups
            if "Old1" in str(parent_id) or file_list_call_count[0] % 2 == 1:
                return {"files": [{"id": "file_id_1", "name": "Torrent1", "kind": "drive#folder"}]}
            else:
                return {"files": [{"id": "file_id_2", "name": "Torrent2", "kind": "drive#folder"}]}

        mock_instance.file_list = AsyncMock(side_effect=file_list_side_effect)
        mock_instance.file_batch_move = AsyncMock(return_value={})

        result = pikpak_downloader.move_torrent([hash1, hash2], "New/Path")

        assert result is True
        mock_instance.file_batch_move.assert_called_once()
        call_args = mock_instance.file_batch_move.call_args
        moved_ids = call_args.kwargs.get("ids", call_args[1].get("ids", []))
        # Both torrents' folders should be moved
        assert len(moved_ids) == 2


@pytest.mark.unit
class TestPikPakThreadSafetyHashMap:
    """Tests for thread-safe hash map operations."""

    def test_add_torrents_updates_database_for_multiple(
        self, pikpak_downloader, mock_pikpak_api, mock_database
    ):
        """Test that add_torrents updates database for multiple torrents."""
        _, mock_instance = mock_pikpak_api
        MockDatabase, mock_db_instance = mock_database

        # Create mock torrent records that will be updated
        mock_torrent1 = MagicMock()
        mock_torrent2 = MagicMock()
        mock_db_instance.torrent.search_by_hash.side_effect = [
            mock_torrent1,
            mock_torrent2,
        ]

        # Add multiple torrents
        urls = [
            "magnet:?xt=urn:btih:1111111111111111111111111111111111111111&dn=ep1",
            "magnet:?xt=urn:btih:2222222222222222222222222222222222222222&dn=ep2",
        ]

        result = pikpak_downloader.add_torrents(torrent_urls=urls, save_path="Test")

        assert result is True
        # Both torrents should have their cloud path set
        assert mock_torrent1.pikpak_cloud_path == "Test"
        assert mock_torrent2.pikpak_cloud_path == "Test"
        # Database update should be called for both
        assert mock_db_instance.torrent.update.call_count == 2

    def test_move_torrent_updates_hash_map_after_success(
        self, pikpak_downloader, mock_pikpak_api
    ):
        """Test that move_torrent only updates hash map after successful move."""
        _, mock_instance = mock_pikpak_api

        test_hash = "abc123def456abc123def456abc123def456abc1"
        original_path = "/AutoBangumi/Old/Path"
        pikpak_downloader._hash_map[test_hash] = original_path

        # Mock for successful move
        mock_instance.offline_list = AsyncMock(
            return_value={
                "tasks": [
                    {
                        "id": "task_1",
                        "name": "Test",
                        "phase": "PHASE_TYPE_COMPLETE",
                        "file_url": f"magnet:?xt=urn:btih:{test_hash}",
                    }
                ]
            }
        )
        mock_instance.path_to_id = AsyncMock(
            return_value=[{"id": "folder_123", "name": "folder"}]
        )
        # Mock file_list to return the file so _find_file_or_folder_id_by_name works
        mock_instance.file_list = AsyncMock(
            return_value={
                "files": [{"id": "file_123", "name": "Test", "kind": "drive#file"}]
            }
        )
        mock_instance.file_batch_move = AsyncMock(return_value={})

        # In real usage, new_location already includes full path from _gen_save_path
        from module.conf import settings

        new_location = f"{settings.downloader.path}/New/Path"
        result = pikpak_downloader.move_torrent([test_hash], new_location)

        assert result is True
        # Hash map should be updated to the new location path directly
        assert pikpak_downloader._hash_map[test_hash] == new_location

    def test_move_torrent_preserves_hash_map_on_failure(
        self, pikpak_downloader, mock_pikpak_api
    ):
        """Test that move_torrent preserves hash map on failure."""
        _, mock_instance = mock_pikpak_api

        test_hash = "abc123def456abc123def456abc123def456abc1"
        original_path = "/AutoBangumi/Old/Path"
        pikpak_downloader._hash_map[test_hash] = original_path

        # Mock for failed move
        mock_instance.offline_list = AsyncMock(
            return_value={
                "tasks": [
                    {
                        "id": "task_1",
                        "name": "Test",
                        "phase": "PHASE_TYPE_COMPLETE",
                        "file_url": f"magnet:?xt=urn:btih:{test_hash}",
                    }
                ]
            }
        )
        mock_instance.path_to_id = AsyncMock(
            return_value=[{"id": "folder_123", "name": "folder"}]
        )
        # Mock file_list to return the file so _find_file_or_folder_id_by_name works
        mock_instance.file_list = AsyncMock(
            return_value={
                "files": [{"id": "file_123", "name": "Test", "kind": "drive#file"}]
            }
        )
        mock_instance.file_batch_move = AsyncMock(
            side_effect=Exception("API Error: Move failed")
        )

        result = pikpak_downloader.move_torrent([test_hash], "New/Path")

        assert result is False
        # Hash map should retain original path
        assert pikpak_downloader._hash_map[test_hash] == original_path


@pytest.mark.unit
class TestPikPakDeleteRetry:
    """Tests for delete operation retry behavior."""

    def test_delete_preserves_hash_on_task_deletion_failure(
        self, pikpak_downloader, mock_pikpak_api
    ):
        """Test that hash is preserved if task deletion fails."""
        _, mock_instance = mock_pikpak_api

        test_hash = "abc123def456abc123def456abc123def456abc1"
        pikpak_downloader._hash_map[test_hash] = "/AutoBangumi/Test"

        # Mock offline_list to return matching task
        mock_instance.offline_list = AsyncMock(
            return_value={
                "tasks": [
                    {
                        "id": "task_1",
                        "file_url": f"magnet:?xt=urn:btih:{test_hash}",
                    }
                ]
            }
        )
        # Mock delete_tasks to fail
        mock_instance.delete_tasks = AsyncMock(
            side_effect=Exception("API Error: Deletion failed")
        )

        # Mock file_list/path_to_id for fallback path (also fails)
        mock_instance.path_to_id = AsyncMock(return_value=[])

        pikpak_downloader.torrents_delete(test_hash)

        # Hash should still be in map (preserved for retry)
        assert test_hash in pikpak_downloader._hash_map

    def test_delete_removes_hash_on_success(self, pikpak_downloader, mock_pikpak_api):
        """Test that hash is removed after successful deletion."""
        _, mock_instance = mock_pikpak_api

        test_hash = "abc123def456abc123def456abc123def456abc1"
        pikpak_downloader._hash_map[test_hash] = "/AutoBangumi/Test"

        # Mock successful deletion
        mock_instance.offline_list = AsyncMock(
            return_value={
                "tasks": [
                    {
                        "id": "task_1",
                        "file_url": f"magnet:?xt=urn:btih:{test_hash}",
                    }
                ]
            }
        )
        mock_instance.delete_tasks = AsyncMock(return_value={})

        pikpak_downloader.torrents_delete(test_hash)

        # Hash should be removed from map
        assert test_hash not in pikpak_downloader._hash_map

    def test_delete_file_fallback_preserves_hash_on_failure(
        self, pikpak_downloader, mock_pikpak_api
    ):
        """Test fallback file deletion preserves hash on failure."""
        _, mock_instance = mock_pikpak_api

        test_hash = "abc123def456abc123def456abc123def456abc1"
        pikpak_downloader._hash_map[test_hash] = "/AutoBangumi/Test"

        # No matching task found
        mock_instance.offline_list = AsyncMock(return_value={"tasks": []})

        # Mock path lookup to find file
        mock_instance.path_to_id = AsyncMock(
            return_value=[{"id": "file_123", "name": "test.mkv"}]
        )

        # Mock delete_to_trash to fail
        mock_instance.delete_to_trash = AsyncMock(
            side_effect=Exception("API Error: Trash failed")
        )

        pikpak_downloader.torrents_delete(test_hash)

        # Hash should still be in map (preserved for retry)
        assert test_hash in pikpak_downloader._hash_map


@pytest.mark.unit
class TestPikPakTimeout:
    """Tests for API timeout handling."""

    def test_api_timeout_constant_exists(self):
        """Test that API_TIMEOUT_SECONDS constant is defined."""
        from module.downloader.client.pikpak_downloader import API_TIMEOUT_SECONDS

        assert isinstance(API_TIMEOUT_SECONDS, (int, float))
        assert API_TIMEOUT_SECONDS > 0
        assert API_TIMEOUT_SECONDS == 60  # Default value

    def test_run_async_handles_timeout(
        self, pikpak_downloader, mock_pikpak_api
    ):
        """Test that _run_async properly handles TimeoutError from AnyIO."""
        _, mock_instance = mock_pikpak_api

        # Mock the portal's call method to raise TimeoutError
        # (portal is already created in __init__, so we mock it on the instance)
        pikpak_downloader._portal = MagicMock()
        pikpak_downloader._portal.call.side_effect = TimeoutError("timed out")

        async def simple_op():
            return "test"

        with pytest.raises(TimeoutError, match="timed out"):
            pikpak_downloader._run_async(simple_op())

    def test_run_async_uses_timeout_constant(self):
        """Test that _run_async references API_TIMEOUT_SECONDS."""
        # Verify the code uses the constant by inspecting the source
        import inspect

        from module.downloader.client.pikpak_downloader import PikPakDownloader

        source = inspect.getsource(PikPakDownloader._run_async)
        assert "API_TIMEOUT_SECONDS" in source
        assert "fail_after" in source


@pytest.mark.unit
class TestPikPakAsyncBridging:
    """Tests for AnyIO async bridging."""

    def test_run_async_uses_blocking_portal(self, pikpak_downloader_with_token, mock_pikpak_api):
        """Test that _run_async uses AnyIO blocking portal."""
        _, mock_instance = mock_pikpak_api

        # Mock the portal's call method on the instance
        # (portal is created in __init__, so we mock it directly)
        mock_portal_call = MagicMock(return_value="test_result")
        pikpak_downloader_with_token._portal = MagicMock()
        pikpak_downloader_with_token._portal.call = mock_portal_call

        async def simple_coro():
            return "test"

        # Use pikpak_downloader_with_token which has a valid token
        # so _ensure_valid_token won't make extra portal calls
        result = pikpak_downloader_with_token._run_async(simple_coro())

        # Portal.call should have been used
        mock_portal_call.assert_called_once()
        assert result == "test_result"

    def test_ensure_valid_token_uses_blocking_portal(self, pikpak_downloader, mock_pikpak_api):
        """Test that _ensure_valid_token uses AnyIO blocking portal for async operations."""
        import time

        _, mock_instance = mock_pikpak_api

        # Set token to expire soon (within 5-minute threshold)
        pikpak_downloader._token_expires_at = int(time.time()) + 120
        pikpak_downloader._client.refresh_token = "test_refresh"

        # Mock the portal's call method on the instance
        # (portal is created in __init__, so we mock it directly)
        mock_portal_call = MagicMock()
        pikpak_downloader._portal = MagicMock()
        pikpak_downloader._portal.call = mock_portal_call

        pikpak_downloader._ensure_valid_token()

        # Portal.call should have been used for refresh_access_token
        mock_portal_call.assert_called_once()


@pytest.mark.unit
class TestPikPakListAllFileIds:
    """Tests for _list_all_file_ids_in_folder helper."""

    def test_list_all_file_ids_returns_empty_for_missing_folder(
        self, pikpak_downloader, mock_pikpak_api
    ):
        """Test that _list_all_file_ids_in_folder returns empty list for missing folder."""
        _, mock_instance = mock_pikpak_api
        mock_instance.path_to_id = AsyncMock(return_value=[])

        result = pikpak_downloader._list_all_file_ids_in_folder("/nonexistent/path")

        assert result == []

    def test_list_all_file_ids_collects_files_only(
        self, pikpak_downloader, mock_pikpak_api
    ):
        """Test that only file IDs are collected, not folder IDs."""
        _, mock_instance = mock_pikpak_api

        mock_instance.path_to_id = AsyncMock(
            return_value=[{"id": "folder_123", "name": "test"}]
        )
        mock_instance.file_list = AsyncMock(
            return_value={
                "files": [
                    {"id": "file_1", "name": "video.mkv", "kind": "drive#file"},
                    {"id": "folder_1", "name": "subs", "kind": "drive#folder"},
                ]
            }
        )

        # Second call for subfolder (empty)
        mock_instance.file_list.side_effect = [
            {
                "files": [
                    {"id": "file_1", "name": "video.mkv", "kind": "drive#file"},
                    {"id": "folder_1", "name": "subs", "kind": "drive#folder"},
                ]
            },
            {"files": []},  # Empty subfolder
        ]

        result = pikpak_downloader._list_all_file_ids_in_folder("/test/path")

        # Should only contain file_1, not folder_1
        assert "file_1" in result
        assert "folder_1" not in result


@pytest.mark.unit
class TestPikPakDatabaseStorage:
    """Tests for database-based path storage."""

    def test_add_torrents_stores_path_in_database(
        self, pikpak_downloader, mock_pikpak_api, mock_database
    ):
        """Test that add_torrents stores pikpak_cloud_path in database."""
        _, mock_instance = mock_pikpak_api
        MockDatabase, mock_db_instance = mock_database

        # Create a mock torrent record
        mock_torrent = MagicMock()
        mock_torrent.name = "Test Torrent"
        mock_db_instance.torrent.search_by_hash.return_value = mock_torrent

        result = pikpak_downloader.add_torrents(
            torrent_urls="magnet:?xt=urn:btih:abc123def456abc123def456abc123def456abc1&dn=test",
            save_path="/AutoBangumi/Test Series/Season 1",
        )

        assert result is True
        # Verify database was queried with the hash
        mock_db_instance.torrent.search_by_hash.assert_called_with(
            "abc123def456abc123def456abc123def456abc1"
        )
        # Verify cloud path was set on the torrent record
        assert mock_torrent.pikpak_cloud_path == "/AutoBangumi/Test Series/Season 1"
        # Verify update was called
        mock_db_instance.torrent.update.assert_called_with(mock_torrent)

    def test_torrents_info_reads_path_from_database(
        self, pikpak_downloader, mock_pikpak_api, mock_database
    ):
        """Test that torrents_info reads pikpak_cloud_path from database."""
        _, mock_instance = mock_pikpak_api
        MockDatabase, mock_db_instance = mock_database

        # Create a mock torrent record with cloud path
        mock_torrent = MagicMock()
        mock_torrent.pikpak_cloud_path = "/AutoBangumi/Test Series/Season 1"
        mock_torrent.renamed_at = None
        mock_db_instance.torrent.search_by_hash.return_value = mock_torrent

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
        # Mock file_list to return files
        mock_instance.file_list = AsyncMock(
            return_value={
                "files": [{"name": "Test Episode 01.mkv", "kind": "drive#file"}]
            }
        )

        result = pikpak_downloader.torrents_info(status_filter="completed")

        assert len(result) == 1
        assert result[0].save_path == "/AutoBangumi/Test Series/Season 1"
        # Verify database was queried
        mock_db_instance.torrent.search_by_hash.assert_called()

    def test_torrents_info_skips_torrent_without_path(
        self, pikpak_downloader, mock_pikpak_api, mock_database
    ):
        """Test that torrents_info skips torrents without cloud path in database."""
        _, mock_instance = mock_pikpak_api
        MockDatabase, mock_db_instance = mock_database

        # Return None for torrent lookup (not in database)
        mock_db_instance.torrent.search_by_hash.return_value = None

        mock_instance.offline_list = AsyncMock(
            return_value={
                "tasks": [
                    {
                        "id": "task_1",
                        "name": "Unknown Torrent.mkv",
                        "phase": "PHASE_TYPE_COMPLETE",
                        "progress": 100,
                        "file_url": "magnet:?xt=urn:btih:unknownhash123456789012345678901234567890",
                    }
                ]
            }
        )

        result = pikpak_downloader.torrents_info(status_filter="completed")

        # Torrent should be skipped (no cloud path)
        assert len(result) == 0

    def test_torrents_info_skips_torrent_with_null_cloud_path(
        self, pikpak_downloader, mock_pikpak_api, mock_database
    ):
        """Test that torrents_info skips torrents with null pikpak_cloud_path."""
        _, mock_instance = mock_pikpak_api
        MockDatabase, mock_db_instance = mock_database

        # Return torrent with null cloud path
        mock_torrent = MagicMock()
        mock_torrent.pikpak_cloud_path = None
        mock_db_instance.torrent.search_by_hash.return_value = mock_torrent

        mock_instance.offline_list = AsyncMock(
            return_value={
                "tasks": [
                    {
                        "id": "task_1",
                        "name": "Test Torrent.mkv",
                        "phase": "PHASE_TYPE_COMPLETE",
                        "progress": 100,
                        "file_url": "magnet:?xt=urn:btih:abc123def456abc123def456abc123def456abc1",
                    }
                ]
            }
        )

        result = pikpak_downloader.torrents_info(status_filter="completed")

        # Torrent should be skipped (null cloud path)
        assert len(result) == 0
