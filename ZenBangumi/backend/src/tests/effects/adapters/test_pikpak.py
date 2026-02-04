import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from zen_bangumi.domain.commands.base import (
    CreateDirectory,
    DeleteTorrent,
    DownloadTorrent,
    RenameFile,
)
from zen_bangumi.effects.result import EffectResult, EffectStatus
from zen_bangumi.effects.adapters.pikpak import PikPakAdapter


@pytest.fixture
def mock_pikpak_client():
    """Mock PikPakApi client."""
    client = AsyncMock()
    client.access_token = "test_access_token"
    client.refresh_token = "test_refresh_token"
    client.login = AsyncMock()
    client.offline_list = AsyncMock(return_value={"tasks": []})
    client.offline_download = AsyncMock(return_value={"task": {"id": "task_123"}})
    client.file_list = AsyncMock(return_value={"files": []})
    client.create_folder = AsyncMock(return_value={"file": {"id": "folder_123"}})
    client.rename = AsyncMock()
    client.file_info = AsyncMock(return_value={"file": {"id": "file_123", "name": "test.mp4"}})
    client.offline_task_delete = AsyncMock()
    return client


@pytest.fixture
def adapter(mock_pikpak_client, monkeypatch, tmp_path):
    """PikPakAdapter with mocked client and temp token file."""
    # Mock the TOKEN_FILE path to use temp directory
    token_file = tmp_path / "pikpak_token.json"
    monkeypatch.setattr("zen_bangumi.effects.adapters.pikpak.TOKEN_FILE", token_file)
    
    # Mock PikPakApi initialization
    def mock_client_init(*args, **kwargs):
        return mock_pikpak_client
    
    monkeypatch.setattr("zen_bangumi.effects.adapters.pikpak.PikPakApi", mock_client_init)
    
    return PikPakAdapter(username="test_user", password="test_pass")


class TestDownloadTorrent:
    """Tests for download_torrent method."""

    @pytest.mark.asyncio
    async def test_download_torrent_success(self, adapter, mock_pikpak_client):
        """Test downloading a new torrent successfully."""
        command = DownloadTorrent(
            torrent_url="magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678",
            save_path="/Bangumi/Test",
            bangumi_id=123
        )
        
        mock_pikpak_client.offline_list.return_value = {"tasks": []}
        mock_pikpak_client.file_list.return_value = {"files": []}
        mock_pikpak_client.create_folder.return_value = {"file": {"id": "folder_123"}}
        mock_pikpak_client.offline_download.return_value = {"task": {"id": "task_123"}}
        
        result = await adapter.download_torrent(command)
        
        assert result.status == EffectStatus.SUCCESS
        assert result.command == command
        assert result.error is None
        mock_pikpak_client.offline_download.assert_called_once()

    @pytest.mark.asyncio
    async def test_download_torrent_idempotent_already_exists(self, adapter, mock_pikpak_client):
        """Test idempotency: downloading a torrent that already exists."""
        torrent_hash = "1234567890abcdef1234567890abcdef12345678"
        command = DownloadTorrent(
            torrent_url=f"magnet:?xt=urn:btih:{torrent_hash}",
            save_path="/Bangumi/Test",
            bangumi_id=123
        )
        
        # Mock existing torrent with matching hash
        existing_task = {
            "id": "task_123",
            "file_id": torrent_hash,
            "name": "Test Torrent"
        }
        mock_pikpak_client.offline_list.return_value = {"tasks": [existing_task]}
        
        result = await adapter.download_torrent(command)
        
        assert result.status == EffectStatus.SKIPPED
        assert result.command == command
        assert "already exists" in result.error.lower()
        mock_pikpak_client.offline_download.assert_not_called()

    @pytest.mark.asyncio
    async def test_download_torrent_invalid_hash(self, adapter, mock_pikpak_client):
        """Test downloading with invalid torrent URL (no hash)."""
        command = DownloadTorrent(
            torrent_url="http://example.com/invalid.torrent",
            save_path="/Bangumi/Test",
            bangumi_id=123
        )
        
        result = await adapter.download_torrent(command)
        
        assert result.status == EffectStatus.FAILED
        assert result.command == command
        assert "Could not extract torrent hash" in result.error
        mock_pikpak_client.offline_download.assert_not_called()

    @pytest.mark.asyncio
    async def test_download_torrent_folder_creation_fails(self, adapter, mock_pikpak_client):
        """Test download fails when folder creation fails."""
        command = DownloadTorrent(
            torrent_url="magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678",
            save_path="/Bangumi/Test",
            bangumi_id=123
        )
        
        mock_pikpak_client.offline_list.return_value = {"tasks": []}
        mock_pikpak_client.file_list.side_effect = Exception("API error")
        
        result = await adapter.download_torrent(command)
        
        assert result.status == EffectStatus.FAILED
        assert result.command == command
        assert "Failed to create folder" in result.error

    @pytest.mark.asyncio
    async def test_download_torrent_api_error(self, adapter, mock_pikpak_client):
        """Test handling API errors during download."""
        command = DownloadTorrent(
            torrent_url="magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678",
            save_path="/Bangumi/Test",
            bangumi_id=123
        )
        
        mock_pikpak_client.offline_list.return_value = {"tasks": []}
        mock_pikpak_client.file_list.return_value = {"files": []}
        mock_pikpak_client.create_folder.return_value = {"file": {"id": "folder_123"}}
        mock_pikpak_client.offline_download.side_effect = Exception("Connection failed")
        
        result = await adapter.download_torrent(command)
        
        assert result.status == EffectStatus.FAILED
        assert result.command == command
        assert "Connection failed" in result.error

    @pytest.mark.asyncio
    async def test_download_torrent_no_task_returned(self, adapter, mock_pikpak_client):
        """Test download fails when API returns no task."""
        command = DownloadTorrent(
            torrent_url="magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678",
            save_path="/Bangumi/Test",
            bangumi_id=123
        )
        
        mock_pikpak_client.offline_list.return_value = {"tasks": []}
        mock_pikpak_client.file_list.return_value = {"files": []}
        mock_pikpak_client.create_folder.return_value = {"file": {"id": "folder_123"}}
        mock_pikpak_client.offline_download.return_value = {}  # No task returned
        
        result = await adapter.download_torrent(command)
        
        assert result.status == EffectStatus.FAILED
        assert result.command == command
        assert "no task" in result.error.lower()


class TestRenameFile:
    """Tests for rename_file method."""

    @pytest.mark.asyncio
    async def test_rename_file_success(self, adapter, mock_pikpak_client):
        """Test renaming a file successfully."""
        command = RenameFile(
            source_path="/Bangumi/Test/old_name.mp4",
            target_path="/Bangumi/Test/new_name.mp4",
            downloader_type="pikpak"
        )
        
        # Mock file finding
        async def mock_find_file(path):
            if "old_name" in path:
                return "file_123"
            elif "new_name" in path:
                return None
            return None
        
        adapter._find_file_by_path = AsyncMock(side_effect=mock_find_file)
        
        result = await adapter.rename_file(command)
        
        assert result.status == EffectStatus.SUCCESS
        assert result.command == command
        assert result.error is None
        mock_pikpak_client.rename.assert_called_once_with(file_id="file_123", name="new_name.mp4")

    @pytest.mark.asyncio
    async def test_rename_file_idempotent_already_renamed(self, adapter, mock_pikpak_client):
        """Test idempotency: file already renamed."""
        command = RenameFile(
            source_path="/Bangumi/Test/old_name.mp4",
            target_path="/Bangumi/Test/new_name.mp4",
            downloader_type="pikpak"
        )
        
        # Mock: target exists, source doesn't (already renamed)
        async def mock_find_file(path):
            if "new_name" in path:
                return "file_123"
            return None
        
        adapter._find_file_by_path = AsyncMock(side_effect=mock_find_file)
        
        result = await adapter.rename_file(command)
        
        assert result.status == EffectStatus.SKIPPED
        assert result.command == command
        assert "already renamed" in result.error.lower()
        mock_pikpak_client.rename.assert_not_called()

    @pytest.mark.asyncio
    async def test_rename_file_source_not_found(self, adapter, mock_pikpak_client):
        """Test rename fails when source file doesn't exist."""
        command = RenameFile(
            source_path="/Bangumi/Test/nonexistent.mp4",
            target_path="/Bangumi/Test/new_name.mp4",
            downloader_type="pikpak"
        )
        
        adapter._find_file_by_path = AsyncMock(return_value=None)
        
        result = await adapter.rename_file(command)
        
        assert result.status == EffectStatus.FAILED
        assert result.command == command
        assert "Source file not found" in result.error
        mock_pikpak_client.rename.assert_not_called()

    @pytest.mark.asyncio
    async def test_rename_file_api_error(self, adapter, mock_pikpak_client):
        """Test handling API errors during rename."""
        command = RenameFile(
            source_path="/Bangumi/Test/old_name.mp4",
            target_path="/Bangumi/Test/new_name.mp4",
            downloader_type="pikpak"
        )
        
        adapter._find_file_by_path = AsyncMock(return_value="file_123")
        mock_pikpak_client.rename.side_effect = Exception("Rename failed")
        
        result = await adapter.rename_file(command)
        
        assert result.status == EffectStatus.FAILED
        assert result.command == command
        assert "Rename failed" in result.error


class TestCreateDirectory:
    """Tests for create_directory method."""

    @pytest.mark.asyncio
    async def test_create_directory_success(self, adapter, mock_pikpak_client):
        """Test creating a new directory successfully."""
        command = CreateDirectory(path="/Bangumi/NewAnime/Season 1")
        
        mock_pikpak_client.file_list.return_value = {"files": []}
        mock_pikpak_client.create_folder.return_value = {"file": {"id": "folder_123"}}
        
        result = await adapter.create_directory(command)
        
        assert result.status == EffectStatus.SUCCESS
        assert result.command == command
        assert result.error is None
        # Should create 3 folders (Bangumi, NewAnime, Season 1)
        assert mock_pikpak_client.create_folder.call_count == 3

    @pytest.mark.asyncio
    async def test_create_directory_idempotent_already_exists(self, adapter, mock_pikpak_client):
        """Test idempotency: directory already exists."""
        command = CreateDirectory(path="/Bangumi/ExistingAnime")
        
        bangumi_folder = {"id": "folder_bangumi", "name": "Bangumi", "kind": "drive#folder"}
        existing_folder = {"id": "folder_123", "name": "ExistingAnime", "kind": "drive#folder"}
        
        call_count = [0]
        def mock_file_list_side_effect(parent_id=""):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"files": [bangumi_folder]}
            else:
                return {"files": [existing_folder]}
        
        mock_pikpak_client.file_list.side_effect = mock_file_list_side_effect
        
        result = await adapter.create_directory(command)
        
        assert result.status == EffectStatus.SUCCESS
        assert result.command == command
        mock_pikpak_client.create_folder.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_directory_api_error(self, adapter, mock_pikpak_client):
        """Test handling API errors during directory creation."""
        command = CreateDirectory(path="/Bangumi/Test")
        
        mock_pikpak_client.file_list.side_effect = Exception("API error")
        
        result = await adapter.create_directory(command)
        
        assert result.status == EffectStatus.FAILED
        assert result.command == command
        assert "Failed to create directory" in result.error

    @pytest.mark.asyncio
    async def test_create_directory_empty_path(self, adapter, mock_pikpak_client):
        """Test creating directory with empty path."""
        command = CreateDirectory(path="/")
        
        result = await adapter.create_directory(command)
        
        assert result.status == EffectStatus.FAILED
        assert result.command == command


class TestDeleteTorrent:
    """Tests for delete_torrent method."""

    @pytest.mark.asyncio
    async def test_delete_torrent_success(self, adapter, mock_pikpak_client):
        """Test deleting a torrent successfully."""
        torrent_hash = "1234567890abcdef1234567890abcdef12345678"
        command = DeleteTorrent(
            torrent_hash=torrent_hash,
            delete_files=True
        )
        
        existing_task = {
            "id": "task_123",
            "file_id": torrent_hash,
            "name": "Test Torrent"
        }
        mock_pikpak_client.offline_list.return_value = {"tasks": [existing_task]}
        
        result = await adapter.delete_torrent(command)
        
        assert result.status == EffectStatus.SUCCESS
        assert result.command == command
        assert result.error is None
        mock_pikpak_client.offline_task_delete.assert_called_once_with(
            task_ids=["task_123"],
            delete_files=True
        )

    @pytest.mark.asyncio
    async def test_delete_torrent_without_files(self, adapter, mock_pikpak_client):
        """Test deleting a torrent without deleting files."""
        torrent_hash = "1234567890abcdef1234567890abcdef12345678"
        command = DeleteTorrent(
            torrent_hash=torrent_hash,
            delete_files=False
        )
        
        existing_task = {
            "id": "task_123",
            "file_id": torrent_hash,
            "name": "Test Torrent"
        }
        mock_pikpak_client.offline_list.return_value = {"tasks": [existing_task]}
        
        result = await adapter.delete_torrent(command)
        
        assert result.status == EffectStatus.SUCCESS
        assert result.command == command
        mock_pikpak_client.offline_task_delete.assert_called_once_with(
            task_ids=["task_123"],
            delete_files=False
        )

    @pytest.mark.asyncio
    async def test_delete_torrent_not_found(self, adapter, mock_pikpak_client):
        """Test deleting a torrent that doesn't exist."""
        command = DeleteTorrent(
            torrent_hash="nonexistent1234567890abcdef1234567890ab",
            delete_files=True
        )
        
        mock_pikpak_client.offline_list.return_value = {"tasks": []}
        
        result = await adapter.delete_torrent(command)
        
        assert result.status == EffectStatus.SKIPPED
        assert result.command == command
        assert "not found" in result.error.lower()
        mock_pikpak_client.offline_task_delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_torrent_api_error(self, adapter, mock_pikpak_client):
        """Test handling API errors during deletion."""
        torrent_hash = "1234567890abcdef1234567890abcdef12345678"
        command = DeleteTorrent(
            torrent_hash=torrent_hash,
            delete_files=True
        )
        
        existing_task = {
            "id": "task_123",
            "file_id": torrent_hash,
            "name": "Test Torrent"
        }
        mock_pikpak_client.offline_list.return_value = {"tasks": [existing_task]}
        mock_pikpak_client.offline_task_delete.side_effect = Exception("Delete failed")
        
        result = await adapter.delete_torrent(command)
        
        assert result.status == EffectStatus.FAILED
        assert result.command == command
        assert "Delete failed" in result.error


class TestGetFileInfo:
    """Tests for get_file_info method."""

    @pytest.mark.asyncio
    async def test_get_file_info_found(self, adapter, mock_pikpak_client):
        """Test getting file info when file exists."""
        file_path = "/Bangumi/Test/episode.mp4"
        
        adapter._find_file_by_path = AsyncMock(return_value="file_123")
        mock_pikpak_client.file_info.return_value = {
            "file": {
                "id": "file_123",
                "name": "episode.mp4",
                "size": 1024000000,
                "kind": "drive#file"
            }
        }
        
        info = await adapter.get_file_info(file_path)
        
        assert info is not None
        assert info["id"] == "file_123"
        assert info["name"] == "episode.mp4"
        assert info["size"] == 1024000000

    @pytest.mark.asyncio
    async def test_get_file_info_not_found(self, adapter, mock_pikpak_client):
        """Test getting file info when file doesn't exist."""
        file_path = "/Bangumi/Test/nonexistent.mp4"
        
        adapter._find_file_by_path = AsyncMock(return_value=None)
        
        info = await adapter.get_file_info(file_path)
        
        assert info is None
        mock_pikpak_client.file_info.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_file_info_api_error(self, adapter, mock_pikpak_client):
        """Test handling API errors when getting file info."""
        file_path = "/Bangumi/Test/episode.mp4"
        
        adapter._find_file_by_path = AsyncMock(return_value="file_123")
        mock_pikpak_client.file_info.side_effect = Exception("API error")
        
        info = await adapter.get_file_info(file_path)
        
        assert info is None


class TestListFiles:
    """Tests for list_files method."""

    @pytest.mark.asyncio
    async def test_list_files_success(self, adapter, mock_pikpak_client):
        """Test listing files in a directory."""
        directory_path = "/Bangumi/Test"
        
        files = [
            {"id": "file_1", "name": "episode1.mp4", "kind": "drive#file"},
            {"id": "file_2", "name": "episode2.mp4", "kind": "drive#file"},
        ]
        mock_pikpak_client.file_list.return_value = {"files": files}
        
        result = await adapter.list_files(directory_path)
        
        assert len(result) == 2
        assert result[0]["name"] == "episode1.mp4"
        assert result[1]["name"] == "episode2.mp4"

    @pytest.mark.asyncio
    async def test_list_files_empty_directory(self, adapter, mock_pikpak_client):
        """Test listing files in an empty directory."""
        directory_path = "/Bangumi/Empty"
        
        mock_pikpak_client.file_list.return_value = {"files": []}
        
        result = await adapter.list_files(directory_path)
        
        assert result == []

    @pytest.mark.asyncio
    async def test_list_files_api_error(self, adapter, mock_pikpak_client):
        """Test handling API errors when listing files."""
        directory_path = "/Bangumi/Test"
        
        mock_pikpak_client.file_list.side_effect = Exception("API error")
        
        result = await adapter.list_files(directory_path)
        
        assert result == []


class TestTokenManagement:
    """Tests for token persistence."""

    @pytest.mark.asyncio
    async def test_save_token(self, adapter, mock_pikpak_client, tmp_path, monkeypatch):
        """Test saving token to file."""
        token_file = tmp_path / "pikpak_token.json"
        monkeypatch.setattr("zen_bangumi.effects.adapters.pikpak.TOKEN_FILE", token_file)
        
        mock_pikpak_client.access_token = "test_access_token"
        mock_pikpak_client.refresh_token = "test_refresh_token"
        adapter.client = mock_pikpak_client
        
        adapter._save_token()
        
        assert token_file.exists()
        with open(token_file, "r") as f:
            data = json.load(f)
        
        assert data["access_token"] == "test_access_token"
        assert data["refresh_token"] == "test_refresh_token"

    @pytest.mark.asyncio
    async def test_load_token_from_file(self, adapter, mock_pikpak_client, tmp_path, monkeypatch):
        """Test loading token from file."""
        token_file = tmp_path / "pikpak_token.json"
        monkeypatch.setattr("zen_bangumi.effects.adapters.pikpak.TOKEN_FILE", token_file)
        
        # Create token file
        token_data = {
            "access_token": "saved_access_token",
            "refresh_token": "saved_refresh_token"
        }
        token_file.parent.mkdir(parents=True, exist_ok=True)
        with open(token_file, "w") as f:
            json.dump(token_data, f)
        
        # Reset adapter state
        adapter._token_data = None
        adapter.client = mock_pikpak_client
        mock_pikpak_client.access_token = "saved_access_token"
        
        await adapter._ensure_authenticated()
        
        assert adapter._token_data is not None
        assert adapter._token_data["access_token"] == "saved_access_token"
        assert adapter._token_data["refresh_token"] == "saved_refresh_token"
        # Should not call login since token was loaded
        mock_pikpak_client.login.assert_not_called()

    @pytest.mark.asyncio
    async def test_authenticate_when_no_token(self, adapter, mock_pikpak_client, tmp_path, monkeypatch):
        """Test authentication when no token file exists."""
        token_file = tmp_path / "pikpak_token.json"
        monkeypatch.setattr("zen_bangumi.effects.adapters.pikpak.TOKEN_FILE", token_file)
        
        adapter._token_data = None
        adapter.client = mock_pikpak_client
        mock_pikpak_client.access_token = None
        mock_pikpak_client.login = AsyncMock()
        mock_pikpak_client.login.return_value = None
        
        await adapter._ensure_authenticated()
        
        mock_pikpak_client.login.assert_called_once()


class TestExtractHash:
    """Tests for _extract_hash method."""

    def test_extract_hash_from_magnet_link(self, adapter):
        """Test extracting hash from magnet link."""
        magnet_url = "magnet:?xt=urn:btih:1234567890ABCDEF1234567890ABCDEF12345678"
        
        hash_value = adapter._extract_hash(magnet_url)
        
        assert hash_value == "1234567890abcdef1234567890abcdef12345678"

    def test_extract_hash_lowercase(self, adapter):
        """Test hash is returned in lowercase."""
        magnet_url = "magnet:?xt=urn:btih:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        
        hash_value = adapter._extract_hash(magnet_url)
        
        assert hash_value == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

    def test_extract_hash_invalid_url(self, adapter):
        """Test extracting hash from invalid URL returns None."""
        invalid_url = "http://example.com/torrent.torrent"
        
        hash_value = adapter._extract_hash(invalid_url)
        
        assert hash_value is None

    def test_extract_hash_empty_string(self, adapter):
        """Test extracting hash from empty string returns None."""
        hash_value = adapter._extract_hash("")
        
        assert hash_value is None
