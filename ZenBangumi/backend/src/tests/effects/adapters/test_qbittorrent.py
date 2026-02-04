import hashlib
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from zen_bangumi.domain.commands.base import DeleteTorrent, DownloadTorrent
from zen_bangumi.effects.adapters.qbittorrent import QBittorrentAdapter
from zen_bangumi.effects.result import EffectResult, EffectStatus


@pytest.fixture
def mock_qb_client():
    """Mock qBittorrent client."""
    client = MagicMock()
    client.torrents_info.return_value = []
    client.torrents_add.return_value = "Ok."
    client.torrents_delete.return_value = None
    return client


@pytest.fixture
def adapter(mock_qb_client, monkeypatch):
    """QBittorrentAdapter with mocked client."""
    def mock_client_init(*args, **kwargs):
        return mock_qb_client
    
    monkeypatch.setattr("zen_bangumi.effects.adapters.qbittorrent.Client", mock_client_init)
    return QBittorrentAdapter(
        host="http://localhost:8080",
        username="admin",
        password="adminpass",
        ssl=False
    )


@pytest.mark.asyncio
async def test_download_torrent_new_torrent(adapter, mock_qb_client):
    """Test downloading a new torrent that doesn't exist."""
    command = DownloadTorrent(
        torrent_url="http://example.com/torrent.torrent",
        save_path="/downloads/anime",
        bangumi_id=123
    )
    
    # No existing torrents
    mock_qb_client.torrents_info.return_value = []
    mock_qb_client.torrents_add.return_value = "Ok."
    
    result = await adapter.download_torrent(command)
    
    assert result.status == EffectStatus.SUCCESS
    assert result.command == command
    assert result.error is None
    mock_qb_client.torrents_add.assert_called_once()


@pytest.mark.asyncio
async def test_download_torrent_idempotent_already_exists(adapter, mock_qb_client):
    """Test idempotency: downloading a torrent that already exists."""
    torrent_url = "http://example.com/torrent.torrent"
    torrent_hash = hashlib.sha1(torrent_url.encode()).hexdigest()
    
    command = DownloadTorrent(
        torrent_url=torrent_url,
        save_path="/downloads/anime",
        bangumi_id=123
    )
    
    # Mock existing torrent with matching hash
    existing_torrent = MagicMock()
    existing_torrent.hash = torrent_hash
    mock_qb_client.torrents_info.return_value = [existing_torrent]
    
    result = await adapter.download_torrent(command)
    
    assert result.status == EffectStatus.SKIPPED
    assert result.command == command
    assert "already exists" in result.error.lower()
    mock_qb_client.torrents_add.assert_not_called()


@pytest.mark.asyncio
async def test_download_torrent_api_error(adapter, mock_qb_client):
    """Test handling API errors during download."""
    command = DownloadTorrent(
        torrent_url="http://example.com/torrent.torrent",
        save_path="/downloads/anime",
        bangumi_id=123
    )
    
    mock_qb_client.torrents_info.return_value = []
    mock_qb_client.torrents_add.side_effect = Exception("Connection failed")
    
    result = await adapter.download_torrent(command)
    
    assert result.status == EffectStatus.FAILED
    assert result.command == command
    assert "Connection failed" in result.error


@pytest.mark.asyncio
async def test_delete_torrent_success(adapter, mock_qb_client):
    """Test deleting a torrent successfully."""
    command = DeleteTorrent(
        torrent_hash="abc123def456",
        delete_files=True
    )
    
    mock_qb_client.torrents_delete.return_value = None
    
    result = await adapter.delete_torrent(command)
    
    assert result.status == EffectStatus.SUCCESS
    assert result.command == command
    assert result.error is None
    mock_qb_client.torrents_delete.assert_called_once_with(
        delete_files=True,
        torrent_hashes="abc123def456"
    )


@pytest.mark.asyncio
async def test_delete_torrent_without_files(adapter, mock_qb_client):
    """Test deleting a torrent without deleting files."""
    command = DeleteTorrent(
        torrent_hash="abc123def456",
        delete_files=False
    )
    
    mock_qb_client.torrents_delete.return_value = None
    
    result = await adapter.delete_torrent(command)
    
    assert result.status == EffectStatus.SUCCESS
    assert result.command == command
    mock_qb_client.torrents_delete.assert_called_once_with(
        delete_files=False,
        torrent_hashes="abc123def456"
    )


@pytest.mark.asyncio
async def test_delete_torrent_api_error(adapter, mock_qb_client):
    """Test handling API errors during deletion."""
    command = DeleteTorrent(
        torrent_hash="abc123def456",
        delete_files=True
    )
    
    mock_qb_client.torrents_delete.side_effect = Exception("Torrent not found")
    
    result = await adapter.delete_torrent(command)
    
    assert result.status == EffectStatus.FAILED
    assert result.command == command
    assert "Torrent not found" in result.error


@pytest.mark.asyncio
async def test_get_torrent_info_found(adapter, mock_qb_client):
    """Test getting torrent info when torrent exists."""
    torrent_hash = "abc123def456"
    
    mock_torrent = MagicMock()
    mock_torrent.hash = torrent_hash
    mock_torrent.name = "Test Anime"
    mock_torrent.progress = 0.5
    mock_torrent.state = "downloading"
    
    mock_qb_client.torrents_info.return_value = [mock_torrent]
    
    info = await adapter.get_torrent_info(torrent_hash)
    
    assert info is not None
    assert info["hash"] == torrent_hash
    assert info["name"] == "Test Anime"
    assert info["progress"] == 0.5
    assert info["state"] == "downloading"


@pytest.mark.asyncio
async def test_get_torrent_info_not_found(adapter, mock_qb_client):
    """Test getting torrent info when torrent doesn't exist."""
    torrent_hash = "nonexistent"
    
    mock_qb_client.torrents_info.return_value = []
    
    info = await adapter.get_torrent_info(torrent_hash)
    
    assert info is None


@pytest.mark.asyncio
async def test_get_torrent_info_api_error(adapter, mock_qb_client):
    """Test handling API errors when getting torrent info."""
    torrent_hash = "abc123def456"
    
    mock_qb_client.torrents_info.side_effect = Exception("API error")
    
    info = await adapter.get_torrent_info(torrent_hash)
    
    assert info is None
