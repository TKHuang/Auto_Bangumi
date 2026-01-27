"""Unit tests for TorrentManager.

This module contains unit tests for the TorrentManager class methods.
"""

from unittest.mock import MagicMock, patch

import pytest

from module.models.bangumi import Bangumi


class TestTorrentManagerDeleteRule:
    """Tests for TorrentManager delete operations."""

    @pytest.mark.unit
    def test_delete_rule_removes_from_db(self, in_memory_engine):
        """Test that delete_rule removes bangumi from database.

        When deleting a rule by ID, the bangumi should be removed from the
        database via bangumi.delete_one().
        """
        # Create mock for DownloadClient
        mock_client = MagicMock()
        mock_client.get_torrent_info.return_value = []
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=None)

        with patch("module.manager.torrent.DownloadClient", return_value=mock_client):
            from module.manager.torrent import TorrentManager

            # Set up database with tables and seed data
            manager = TorrentManager(engine=in_memory_engine)
            manager.create_table()

            # Add a bangumi to delete
            bangumi = Bangumi(
                id=1,
                rss_id=1,
                official_title="Test Anime",
                title_raw="[TestGroup] Test Anime",
                season=1,
                group_name="TestGroup",
                rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=12345",
                save_path="/downloads/Test Anime",
            )
            manager.add(bangumi)
            manager.commit()

            # Verify bangumi exists
            assert manager.bangumi.search_id(1) is not None

            # Delete the rule (without deleting files)
            result = manager.delete_rule(1, file=False)

            # Verify deletion succeeded
            assert result.status is True
            assert result.status_code == 200
            assert "Test Anime" in result.msg_en

            # Verify bangumi is removed from database
            assert manager.bangumi.search_id(1) is None

    @pytest.mark.unit
    def test_delete_with_file_removes_from_qbittorrent(self, in_memory_engine):
        """Test that delete_rule with file=True removes torrents from qBittorrent.

        When deleting a rule with file=True, the associated torrents should be
        deleted from qBittorrent via client.delete_torrent().
        """
        save_path = "/downloads/Test Anime"

        # Create mock torrent with matching save path
        mock_torrent = MagicMock()
        mock_torrent.hash = "abc123def456"
        mock_torrent.save_path = save_path

        # Create mock for DownloadClient
        mock_client = MagicMock()
        mock_client.get_torrent_info.return_value = [mock_torrent]
        mock_client.delete_torrent.return_value = True
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=None)

        with patch("module.manager.torrent.DownloadClient", return_value=mock_client):
            from module.manager.torrent import TorrentManager

            # Set up database with tables and seed data
            manager = TorrentManager(engine=in_memory_engine)
            manager.create_table()

            # Add a bangumi with a save path
            bangumi = Bangumi(
                id=1,
                rss_id=1,
                official_title="Test Anime",
                title_raw="[TestGroup] Test Anime",
                season=1,
                group_name="TestGroup",
                rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=12345",
                save_path=save_path,
            )
            manager.add(bangumi)
            manager.commit()

            # Delete the rule with file=True
            result = manager.delete_rule(1, file=True)

            # Verify deletion succeeded
            assert result.status is True
            assert result.status_code == 200
            assert "Test Anime" in result.msg_en

            # Verify torrent was deleted from qBittorrent
            mock_client.delete_torrent.assert_called_once_with(["abc123def456"])

    @pytest.mark.unit
    def test_delete_many_rules_works(self, in_memory_engine):
        """Test that delete_many_rules batch deletes multiple bangumi.

        When provided with a list of IDs, the method should delete all
        bangumi in a single batch operation.
        """
        # Create mock for DownloadClient
        mock_client = MagicMock()
        mock_client.get_torrent_info.return_value = []
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=None)

        with patch("module.manager.torrent.DownloadClient", return_value=mock_client):
            from module.manager.torrent import TorrentManager

            # Set up database with tables and seed data
            manager = TorrentManager(engine=in_memory_engine)
            manager.create_table()

            # Add multiple bangumi to delete
            bangumi1 = Bangumi(
                id=1,
                rss_id=1,
                official_title="Test Anime 1",
                title_raw="[TestGroup] Test Anime 1",
                season=1,
                group_name="TestGroup",
                rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=12345",
            )
            bangumi2 = Bangumi(
                id=2,
                rss_id=1,
                official_title="Test Anime 2",
                title_raw="[TestGroup] Test Anime 2",
                season=1,
                group_name="TestGroup",
                rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=12346",
            )
            bangumi3 = Bangumi(
                id=3,
                rss_id=2,
                official_title="Test Anime 3",
                title_raw="[TestGroup] Test Anime 3",
                season=1,
                group_name="TestGroup",
                rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=12347",
            )
            manager.add(bangumi1)
            manager.add(bangumi2)
            manager.add(bangumi3)
            manager.commit()

            # Verify all bangumi exist
            assert manager.bangumi.search_id(1) is not None
            assert manager.bangumi.search_id(2) is not None
            assert manager.bangumi.search_id(3) is not None

            # Delete two of the rules
            result = manager.delete_many_rules([1, 2], file=False)

            # Verify batch deletion succeeded
            assert result.status is True
            assert result.status_code == 200
            assert "Deleted 2" in result.msg_en

            # Verify only the deleted bangumi are removed
            assert manager.bangumi.search_id(1) is None
            assert manager.bangumi.search_id(2) is None
            assert manager.bangumi.search_id(3) is not None  # Should still exist

    @pytest.mark.unit
    def test_delete_nonexistent_returns_error(self, in_memory_engine):
        """Test that delete_rule returns error for nonexistent ID.

        When trying to delete a bangumi that doesn't exist, the method
        should return a ResponseModel with status=False.
        """
        # Create mock for DownloadClient
        mock_client = MagicMock()
        mock_client.get_torrent_info.return_value = []
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=None)

        with patch("module.manager.torrent.DownloadClient", return_value=mock_client):
            from module.manager.torrent import TorrentManager

            # Set up database with tables but no data
            manager = TorrentManager(engine=in_memory_engine)
            manager.create_table()

            # Try to delete nonexistent rule
            result = manager.delete_rule(999, file=False)

            # Verify error response
            assert result.status is False
            assert result.status_code == 406
            assert "999" in result.msg_en

    @pytest.mark.unit
    def test_disable_enable_toggle_deleted_flag(self, in_memory_engine):
        """Test that disable/enable toggle the deleted flag.

        Disable should set deleted=True, enable should set deleted=False.
        The bangumi should remain in the database but be marked as disabled.
        """
        # Create mock for DownloadClient
        mock_client = MagicMock()
        mock_client.get_torrent_info.return_value = []
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=None)

        with patch("module.manager.torrent.DownloadClient", return_value=mock_client):
            from module.manager.torrent import TorrentManager

            # Set up database with tables and seed data
            manager = TorrentManager(engine=in_memory_engine)
            manager.create_table()

            # Add a bangumi to toggle
            bangumi = Bangumi(
                id=1,
                rss_id=1,
                official_title="Test Anime",
                title_raw="[TestGroup] Test Anime",
                season=1,
                group_name="TestGroup",
                rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=12345",
                deleted=False,
            )
            manager.add(bangumi)
            manager.commit()

            # Verify initial state: not deleted
            data = manager.bangumi.search_id(1)
            assert data.deleted is False

            # Disable the rule
            result = manager.disable_rule(1, file=False)
            assert result.status is True
            assert result.status_code == 200
            assert "Disable" in result.msg_en

            # Verify bangumi still exists but is marked as deleted
            data = manager.bangumi.search_id(1)
            assert data is not None
            assert data.deleted is True

            # Enable the rule
            result = manager.enable_rule(1)
            assert result.status is True
            assert result.status_code == 200
            assert "Enable" in result.msg_en

            # Verify bangumi is now enabled
            data = manager.bangumi.search_id(1)
            assert data is not None
            assert data.deleted is False
