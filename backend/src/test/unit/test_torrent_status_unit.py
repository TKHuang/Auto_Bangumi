"""Unit tests for TorrentStatusManager.

This module contains unit tests for the TorrentStatusManager class methods.
"""

from unittest.mock import MagicMock, patch

import pytest

from module.models.bangumi import Bangumi
from module.models.rss import RSSItem
from module.models.torrent import Torrent


class TestTorrentStatusManager:
    """Tests for TorrentStatusManager get and download operations."""

    @pytest.mark.unit
    def test_get_bangumi_torrents_status_returns_correct_status(self, in_memory_engine):
        """Test that get_bangumi_torrents_status returns correct torrent status.

        When getting status for a bangumi, torrents that exist in both database
        and qBittorrent should have their qBittorrent state and progress included.
        """
        # Create mock qBittorrent torrent response
        mock_qb_torrent = MagicMock()
        mock_qb_torrent.hash = "abc123def456"
        mock_qb_torrent.state = "downloading"
        mock_qb_torrent.progress = 0.75

        # Create mock for DownloadClient
        mock_client = MagicMock()
        mock_client.get_torrent_info.return_value = [mock_qb_torrent]
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=None)

        with patch(
            "module.manager.torrent_status.DownloadClient", return_value=mock_client
        ):
            from module.manager.torrent_status import TorrentStatusManager

            # Set up database with tables and seed data
            manager = TorrentStatusManager(engine=in_memory_engine)
            manager.create_table()

            # Add an RSS item first (required for foreign key)
            rss_item = RSSItem(
                id=1,
                name="Test RSS Feed",
                url="https://mikanani.me/RSS/MyBangumi?bangumiId=12345",
                aggregate=False,
            )
            manager.add(rss_item)
            manager.commit()

            # Add a bangumi
            bangumi = Bangumi(
                id=1,
                rss_id=1,
                official_title="Test Anime",
                title_raw="[TestGroup] Test Anime",
                season=1,
                group_name="TestGroup",
                rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=12345",
            )
            manager.add(bangumi)
            manager.commit()

            # Add a torrent linked to the bangumi with matching hash
            # Note: use refer_id (the alias) to set bangumi_id via constructor
            torrent = Torrent(
                id=1,
                name="[TestGroup] Test Anime - 01.mkv",
                url="https://example.com/torrent1.torrent",
                refer_id=1,
                rss_id=1,
                hash="abc123def456",
                downloaded=True,
            )
            manager.add(torrent)
            manager.commit()

            # Get torrents status for bangumi
            status_list = manager.get_bangumi_torrents_status(bangumi_id=1)

            # Verify correct status is returned
            assert len(status_list) == 1
            assert status_list[0]["id"] == 1
            assert status_list[0]["name"] == "[TestGroup] Test Anime - 01.mkv"
            assert status_list[0]["status"] == "downloading"
            assert status_list[0]["progress"] == 0.75
            assert status_list[0]["hash"] == "abc123def456"
            assert status_list[0]["downloaded"] is True

    @pytest.mark.unit
    def test_missing_from_qbittorrent_marked_as_missing(self, in_memory_engine):
        """Test that torrents missing from qBittorrent are marked as 'missing'.

        When a torrent exists in the database but not in qBittorrent,
        the status should be set to 'missing' with progress 0.
        """
        # Create mock for DownloadClient (empty response - no torrents in qB)
        mock_client = MagicMock()
        mock_client.get_torrent_info.return_value = []
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=None)

        with patch(
            "module.manager.torrent_status.DownloadClient", return_value=mock_client
        ):
            from module.manager.torrent_status import TorrentStatusManager

            # Set up database with tables and seed data
            manager = TorrentStatusManager(engine=in_memory_engine)
            manager.create_table()

            # Add an RSS item first (required for foreign key)
            rss_item = RSSItem(
                id=1,
                name="Test RSS Feed",
                url="https://mikanani.me/RSS/MyBangumi?bangumiId=12345",
                aggregate=False,
            )
            manager.add(rss_item)
            manager.commit()

            # Add a bangumi
            bangumi = Bangumi(
                id=1,
                rss_id=1,
                official_title="Test Anime",
                title_raw="[TestGroup] Test Anime",
                season=1,
                group_name="TestGroup",
                rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=12345",
            )
            manager.add(bangumi)
            manager.commit()

            # Add a torrent that should exist but doesn't in qBittorrent
            # Note: use refer_id (the alias) to set bangumi_id via constructor
            torrent = Torrent(
                id=1,
                name="[TestGroup] Test Anime - 01.mkv",
                url="https://example.com/torrent1.torrent",
                refer_id=1,
                rss_id=1,
                hash="missing123",
                downloaded=True,
            )
            manager.add(torrent)
            manager.commit()

            # Get torrents status for bangumi
            status_list = manager.get_bangumi_torrents_status(bangumi_id=1)

            # Verify torrent is marked as missing
            assert len(status_list) == 1
            assert status_list[0]["id"] == 1
            assert status_list[0]["name"] == "[TestGroup] Test Anime - 01.mkv"
            assert status_list[0]["status"] == "missing"
            assert status_list[0]["progress"] == 0
            assert status_list[0]["hash"] == "missing123"

    @pytest.mark.unit
    def test_download_torrent_readds_to_qbittorrent(self, in_memory_engine):
        """Test that download_torrent re-adds torrent to qBittorrent.

        When download_torrent is called for a valid torrent with an associated
        bangumi rule, it should call client.add_torrent and update the database.
        """
        # Create mock for DownloadClient
        mock_client = MagicMock()
        mock_client.add_torrent.return_value = True
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=None)

        with patch(
            "module.manager.torrent_status.DownloadClient", return_value=mock_client
        ):
            from module.manager.torrent_status import TorrentStatusManager

            # Set up database with tables and seed data
            manager = TorrentStatusManager(engine=in_memory_engine)
            manager.create_table()

            # Add an RSS item first (required for foreign key)
            rss_item = RSSItem(
                id=1,
                name="Test RSS Feed",
                url="https://mikanani.me/RSS/MyBangumi?bangumiId=12345",
                aggregate=False,
            )
            manager.add(rss_item)
            manager.commit()

            # Add a bangumi
            bangumi = Bangumi(
                id=1,
                rss_id=1,
                official_title="Test Anime",
                title_raw="[TestGroup] Test Anime",
                season=1,
                group_name="TestGroup",
                rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=12345",
            )
            manager.add(bangumi)
            manager.commit()

            # Add a torrent linked to the bangumi
            # Note: use refer_id (the alias) to set bangumi_id via constructor
            torrent = Torrent(
                id=1,
                name="[TestGroup] Test Anime - 01.mkv",
                url="https://example.com/torrent1.torrent",
                refer_id=1,
                rss_id=1,
                hash="abc123",
                downloaded=False,
            )
            manager.add(torrent)
            manager.commit()

            # Download (re-add) the torrent
            result = manager.download_torrent(torrent_id=1)

            # Verify success
            assert result.status is True
            assert result.status_code == 200
            assert "successfully" in result.msg_en.lower()

            # Verify add_torrent was called
            mock_client.add_torrent.assert_called_once()

            # Verify torrent is marked as downloaded in database
            updated_torrent = manager.torrent.search(1)
            assert updated_torrent.downloaded is True

    @pytest.mark.unit
    def test_download_nonexistent_returns_error(self, in_memory_engine):
        """Test that download_torrent returns error for nonexistent torrent.

        When trying to download a torrent that doesn't exist in the database,
        the method should return a ResponseModel with status=False.
        """
        # Create mock for DownloadClient
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=None)

        with patch(
            "module.manager.torrent_status.DownloadClient", return_value=mock_client
        ):
            from module.manager.torrent_status import TorrentStatusManager

            # Set up database with tables but no data
            manager = TorrentStatusManager(engine=in_memory_engine)
            manager.create_table()

            # Try to download nonexistent torrent
            result = manager.download_torrent(torrent_id=999)

            # Verify error response
            assert result.status is False
            assert result.status_code == 406
            assert "not found" in result.msg_en.lower()
