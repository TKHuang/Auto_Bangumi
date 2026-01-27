"""Unit tests for RSSEngine.

This module contains unit tests for the RSSEngine class methods.
"""

from unittest.mock import MagicMock, patch

import pytest

from module.models import ResponseModel, RSSItem
from module.models.bangumi import Bangumi
from module.models.torrent import Torrent
from module.rss import RSSEngine


class TestRSSEngineAddRSS:
    """Tests for RSSEngine.add_rss method."""

    @pytest.mark.unit
    def test_add_non_aggregate_rss_success(
        self, in_memory_engine, mock_request_content, mock_download_client
    ):
        """Test adding a non-aggregate RSS feed succeeds."""
        mock_request_content.get_rss_title.return_value = "Test Non-Aggregate Feed"

        engine = RSSEngine(_engine=in_memory_engine)
        engine.create_table()

        result = engine.add_rss(
            rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=99999",
            name="My Non-Aggregate Feed",
            aggregate=False,
            parser="mikan",
        )

        assert isinstance(result, ResponseModel)
        assert result.status is True
        assert result.status_code == 200
        assert "success" in result.msg_en.lower()

        # Verify RSS was added to database
        rss_items = engine.rss.search_all()
        assert len(rss_items) == 1
        assert rss_items[0].name == "My Non-Aggregate Feed"
        assert rss_items[0].aggregate is False

    @pytest.mark.unit
    def test_add_aggregate_rss_success(
        self, in_memory_engine, mock_request_content, mock_download_client
    ):
        """Test adding an aggregate RSS feed succeeds."""
        mock_request_content.get_rss_title.return_value = "Test Aggregate Feed"

        engine = RSSEngine(_engine=in_memory_engine)
        engine.create_table()

        result = engine.add_rss(
            rss_link="https://mikanani.me/RSS/MyBangumi?token=abc123",
            name="My Aggregate Feed",
            aggregate=True,
            parser="mikan",
        )

        assert isinstance(result, ResponseModel)
        assert result.status is True
        assert result.status_code == 200

        # Verify RSS was added with aggregate=True
        rss_items = engine.rss.search_all()
        assert len(rss_items) == 1
        assert rss_items[0].aggregate is True

    @pytest.mark.unit
    def test_add_rss_without_name_fetches_title(
        self, in_memory_engine, mock_download_client
    ):
        """Test adding RSS without name fetches title from feed."""
        from unittest.mock import MagicMock, patch

        # Create mock for RequestContent with specific return value
        mock_req = MagicMock()
        mock_req.get_rss_title.return_value = "Fetched Feed Title"
        mock_req.__enter__.return_value = mock_req
        mock_req.__exit__.return_value = None

        engine = RSSEngine(_engine=in_memory_engine)
        engine.create_table()

        with patch(
            "module.rss.engine.RequestContent",
            return_value=mock_req,
        ):
            result = engine.add_rss(
                rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=12345",
                name=None,  # No name provided
                aggregate=False,
            )

        assert result.status is True

        # Verify name was fetched from RSS
        rss_items = engine.rss.search_all()
        assert len(rss_items) == 1
        assert rss_items[0].name == "Fetched Feed Title"

    @pytest.mark.unit
    def test_add_duplicate_url_fails(
        self, in_memory_engine, mock_request_content, mock_download_client
    ):
        """Test adding RSS with duplicate URL fails."""
        engine = RSSEngine(_engine=in_memory_engine)
        engine.create_table()

        # Add first RSS
        result1 = engine.add_rss(
            rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=12345",
            name="First Feed",
            aggregate=False,
        )
        assert result1.status is True

        # Try to add duplicate URL
        result2 = engine.add_rss(
            rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=12345",
            name="Second Feed",
            aggregate=False,
        )

        assert result2.status is False
        assert result2.status_code == 406
        assert (
            "already exists" in result2.msg_en.lower()
            or "failed" in result2.msg_en.lower()
        )

    @pytest.mark.unit
    def test_add_rss_invalid_url_fails(self, in_memory_engine, mock_download_client):
        """Test adding RSS with invalid URL (no title returned) fails."""
        from unittest.mock import MagicMock, patch

        # Create mock for RequestContent that returns None (invalid URL)
        mock_req = MagicMock()
        mock_req.get_rss_title.return_value = None
        mock_req.__enter__.return_value = mock_req
        mock_req.__exit__.return_value = None

        engine = RSSEngine(_engine=in_memory_engine)
        engine.create_table()

        with patch(
            "module.rss.engine.RequestContent",
            return_value=mock_req,
        ):
            result = engine.add_rss(
                rss_link="https://invalid-url.com/not-rss",
                name=None,  # No name, so will try to fetch
                aggregate=False,
            )

        assert result.status is False
        assert result.status_code == 406
        assert "invalid" in result.msg_en.lower()

    @pytest.mark.unit
    def test_add_rss_parser_types_stored_correctly(
        self, in_memory_engine, mock_request_content, mock_download_client
    ):
        """Test that parser types are stored correctly in database."""
        engine = RSSEngine(_engine=in_memory_engine)
        engine.create_table()

        # Test mikan parser
        result1 = engine.add_rss(
            rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=11111",
            name="Mikan Feed",
            aggregate=False,
            parser="mikan",
        )
        assert result1.status is True

        # Test tmdb parser
        result2 = engine.add_rss(
            rss_link="https://example.com/rss/feed1",
            name="TMDB Feed",
            aggregate=False,
            parser="tmdb",
        )
        assert result2.status is True

        # Test raw parser
        result3 = engine.add_rss(
            rss_link="https://example.com/rss/feed2",
            name="Raw Feed",
            aggregate=False,
            parser="raw",
        )
        assert result3.status is True

        # Verify all parser types are stored correctly
        rss_items = engine.rss.search_all()
        assert len(rss_items) == 3

        parsers = {item.name: item.parser for item in rss_items}
        assert parsers["Mikan Feed"] == "mikan"
        assert parsers["TMDB Feed"] == "tmdb"
        assert parsers["Raw Feed"] == "raw"


class TestRSSEngineRefreshRSS:
    """Tests for RSSEngine.refresh_rss method."""

    @pytest.mark.unit
    def test_refresh_all_rss(self, in_memory_engine, mock_download_client):
        """Test refreshing all active RSS feeds."""
        engine = RSSEngine(_engine=in_memory_engine)
        engine.create_table()

        # Add two active RSS items
        rss1 = RSSItem(
            id=1,
            name="Feed One",
            url="https://example.com/rss1",
            aggregate=False,
            enabled=True,
        )
        rss2 = RSSItem(
            id=2,
            name="Feed Two",
            url="https://example.com/rss2",
            aggregate=False,
            enabled=True,
        )
        engine.rss.add(rss1)
        engine.rss.add(rss2)

        # Mock RequestContent to return empty torrents
        mock_req = MagicMock()
        mock_req.get_torrents.return_value = []
        mock_req.__enter__.return_value = mock_req
        mock_req.__exit__.return_value = None

        with patch(
            "module.rss.engine.RequestContent",
            return_value=mock_req,
        ):
            engine.refresh_rss(mock_download_client, rss_id=None)

        # Verify both RSS items were processed (checked for torrents)
        assert mock_req.get_torrents.call_count == 2

        # Verify last_status is updated
        updated_rss1 = engine.rss.search_id(1)
        updated_rss2 = engine.rss.search_id(2)
        assert updated_rss1.last_status == "Success"
        assert updated_rss2.last_status == "Success"

    @pytest.mark.unit
    def test_refresh_single_rss_by_id(self, in_memory_engine, mock_download_client):
        """Test refreshing a single RSS feed by ID."""
        engine = RSSEngine(_engine=in_memory_engine)
        engine.create_table()

        # Add two RSS items
        rss1 = RSSItem(
            id=1,
            name="Feed One",
            url="https://example.com/rss1",
            aggregate=False,
            enabled=True,
        )
        rss2 = RSSItem(
            id=2,
            name="Feed Two",
            url="https://example.com/rss2",
            aggregate=False,
            enabled=True,
        )
        engine.rss.add(rss1)
        engine.rss.add(rss2)

        # Mock RequestContent
        mock_req = MagicMock()
        mock_req.get_torrents.return_value = []
        mock_req.__enter__.return_value = mock_req
        mock_req.__exit__.return_value = None

        with patch(
            "module.rss.engine.RequestContent",
            return_value=mock_req,
        ):
            engine.refresh_rss(mock_download_client, rss_id=1)

        # Only first RSS should be processed
        assert mock_req.get_torrents.call_count == 1

        # Only first RSS should have updated status
        updated_rss1 = engine.rss.search_id(1)
        updated_rss2 = engine.rss.search_id(2)
        assert updated_rss1.last_status == "Success"
        assert updated_rss2.last_status is None

    @pytest.mark.unit
    def test_new_matching_torrents_downloaded(
        self, in_memory_engine, mock_download_client
    ):
        """Test that new torrents matching a Bangumi rule are downloaded."""
        engine = RSSEngine(_engine=in_memory_engine)
        engine.create_table()

        # Add RSS item
        rss = RSSItem(
            id=1,
            name="Test Feed",
            url="https://example.com/rss",
            aggregate=False,
            enabled=True,
        )
        engine.rss.add(rss)

        # Add Bangumi rule that will match our torrent
        bangumi = Bangumi(
            id=1,
            rss_id=1,
            official_title="My Anime",
            title_raw="[TestGroup] My Anime",
            season=1,
            group_name="TestGroup",
            rss_link="https://example.com/rss",
            filter="",  # No filter
        )
        engine.bangumi.add(bangumi)

        # Create a torrent that will be returned from RSS
        torrent = Torrent(
            name="[TestGroup] My Anime - 02 [1080p].mkv",
            url="https://example.com/torrent2.torrent",
            hash="newhash123",
        )

        # Mock RequestContent to return our torrent
        mock_req = MagicMock()
        mock_req.get_torrents.return_value = [torrent]
        mock_req.__enter__.return_value = mock_req
        mock_req.__exit__.return_value = None

        with patch(
            "module.rss.engine.RequestContent",
            return_value=mock_req,
        ):
            engine.refresh_rss(mock_download_client, rss_id=1)

        # Verify add_torrent was called
        mock_download_client.add_torrent.assert_called_once()

        # Verify torrent was added to database
        all_torrents = engine.torrent.search_all()
        assert len(all_torrents) == 1
        assert "[TestGroup] My Anime - 02" in all_torrents[0].name

    @pytest.mark.unit
    def test_filtered_torrents_skipped(self, in_memory_engine, mock_download_client):
        """Test that torrents matching filter pattern are skipped."""
        engine = RSSEngine(_engine=in_memory_engine)
        engine.create_table()

        # Add RSS item
        rss = RSSItem(
            id=1,
            name="Test Feed",
            url="https://example.com/rss",
            aggregate=False,
            enabled=True,
        )
        engine.rss.add(rss)

        # Add Bangumi rule with filter to exclude 720p
        bangumi = Bangumi(
            id=1,
            rss_id=1,
            official_title="My Anime",
            title_raw="[TestGroup] My Anime",
            season=1,
            group_name="TestGroup",
            rss_link="https://example.com/rss",
            filter="720",  # Filter out 720p
        )
        engine.bangumi.add(bangumi)

        # Create a 720p torrent that should be filtered
        torrent = Torrent(
            name="[TestGroup] My Anime - 03 [720p].mkv",
            url="https://example.com/torrent3.torrent",
            hash="filtered123",
        )

        # Mock RequestContent to return our torrent
        mock_req = MagicMock()
        mock_req.get_torrents.return_value = [torrent]
        mock_req.__enter__.return_value = mock_req
        mock_req.__exit__.return_value = None

        with patch(
            "module.rss.engine.RequestContent",
            return_value=mock_req,
        ):
            engine.refresh_rss(mock_download_client, rss_id=1)

        # Verify add_torrent was NOT called (filtered out)
        mock_download_client.add_torrent.assert_not_called()

        # Verify torrent was NOT added to database
        all_torrents = engine.torrent.search_all()
        assert len(all_torrents) == 0

    @pytest.mark.unit
    def test_unmatched_torrents_skipped(self, in_memory_engine, mock_download_client):
        """Test that torrents with no matching Bangumi rule are skipped."""
        engine = RSSEngine(_engine=in_memory_engine)
        engine.create_table()

        # Add RSS item (no Bangumi rules exist)
        rss = RSSItem(
            id=1,
            name="Test Feed",
            url="https://example.com/rss",
            aggregate=False,
            enabled=True,
        )
        engine.rss.add(rss)

        # Create a torrent with no matching Bangumi
        torrent = Torrent(
            name="[OtherGroup] Unknown Anime - 01 [1080p].mkv",
            url="https://example.com/unknown.torrent",
            hash="unknown123",
        )

        # Mock RequestContent to return our torrent
        mock_req = MagicMock()
        mock_req.get_torrents.return_value = [torrent]
        mock_req.__enter__.return_value = mock_req
        mock_req.__exit__.return_value = None

        with patch(
            "module.rss.engine.RequestContent",
            return_value=mock_req,
        ):
            engine.refresh_rss(mock_download_client, rss_id=1)

        # Verify add_torrent was NOT called (no match)
        mock_download_client.add_torrent.assert_not_called()

        # Verify torrent was NOT added to database
        all_torrents = engine.torrent.search_all()
        assert len(all_torrents) == 0

    @pytest.mark.unit
    def test_network_errors_recorded(self, in_memory_engine, mock_download_client):
        """Test that network errors are recorded in RSS item status."""
        engine = RSSEngine(_engine=in_memory_engine)
        engine.create_table()

        # Add RSS item
        rss = RSSItem(
            id=1,
            name="Test Feed",
            url="https://example.com/rss",
            aggregate=False,
            enabled=True,
        )
        engine.rss.add(rss)

        # Mock RequestContent to raise an exception
        mock_req = MagicMock()
        mock_req.get_torrents.side_effect = Exception("Network timeout")
        mock_req.__enter__.return_value = mock_req
        mock_req.__exit__.return_value = None

        with patch(
            "module.rss.engine.RequestContent",
            return_value=mock_req,
        ):
            engine.refresh_rss(mock_download_client, rss_id=1)

        # Verify error status is recorded
        updated_rss = engine.rss.search_id(1)
        assert updated_rss.last_status == "Error"
        assert "Network timeout" in updated_rss.last_error


class TestRSSEngineDeleteRSS:
    """Tests for RSSEngine delete operations."""

    @pytest.mark.unit
    def test_delete_single_rss_by_id(self, in_memory_engine, mock_download_client):
        """Test deleting a single RSS feed by ID."""
        engine = RSSEngine(_engine=in_memory_engine)
        engine.create_table()

        # Add RSS items
        rss1 = RSSItem(
            id=1,
            name="Feed One",
            url="https://example.com/rss1",
            aggregate=False,
            enabled=True,
        )
        rss2 = RSSItem(
            id=2,
            name="Feed Two",
            url="https://example.com/rss2",
            aggregate=False,
            enabled=True,
        )
        engine.rss.add(rss1)
        engine.rss.add(rss2)

        # Verify both exist
        assert len(engine.rss.search_all()) == 2

        # Delete single RSS by ID using delete_list with single item
        result = engine.delete_list([1])

        assert isinstance(result, ResponseModel)
        assert result.status is True
        assert result.status_code == 200
        assert "success" in result.msg_en.lower()

        # Verify only one RSS remains
        remaining = engine.rss.search_all()
        assert len(remaining) == 1
        assert remaining[0].id == 2
        assert remaining[0].name == "Feed Two"

        # Verify deleted RSS no longer exists
        assert engine.rss.search_id(1) is None

    @pytest.mark.unit
    def test_delete_multiple_rss_batch(self, in_memory_engine, mock_download_client):
        """Test deleting multiple RSS feeds in a batch operation."""
        engine = RSSEngine(_engine=in_memory_engine)
        engine.create_table()

        # Add three RSS items
        rss1 = RSSItem(
            id=1,
            name="Feed One",
            url="https://example.com/rss1",
            aggregate=False,
            enabled=True,
        )
        rss2 = RSSItem(
            id=2,
            name="Feed Two",
            url="https://example.com/rss2",
            aggregate=False,
            enabled=True,
        )
        rss3 = RSSItem(
            id=3,
            name="Feed Three",
            url="https://example.com/rss3",
            aggregate=False,
            enabled=True,
        )
        engine.rss.add(rss1)
        engine.rss.add(rss2)
        engine.rss.add(rss3)

        # Verify all three exist
        assert len(engine.rss.search_all()) == 3

        # Delete multiple RSS items at once
        result = engine.delete_list([1, 3])

        assert isinstance(result, ResponseModel)
        assert result.status is True
        assert result.status_code == 200

        # Verify only one RSS remains (ID 2)
        remaining = engine.rss.search_all()
        assert len(remaining) == 1
        assert remaining[0].id == 2
        assert remaining[0].name == "Feed Two"

    @pytest.mark.unit
    def test_delete_nonexistent_returns_success(
        self, in_memory_engine, mock_download_client
    ):
        """Test deleting nonexistent RSS ID still returns success response.

        Note: RSSEngine.delete_list always returns success ResponseModel,
        even when underlying rss.delete() returns False for nonexistent IDs.
        This tests the current behavior of the API.
        """
        engine = RSSEngine(_engine=in_memory_engine)
        engine.create_table()

        # Add one RSS item
        rss = RSSItem(
            id=1,
            name="Existing Feed",
            url="https://example.com/rss1",
            aggregate=False,
            enabled=True,
        )
        engine.rss.add(rss)

        # Try to delete nonexistent ID
        result = engine.delete_list([999])

        # RSSEngine.delete_list returns success regardless of individual delete results
        assert isinstance(result, ResponseModel)
        assert result.status is True
        assert result.status_code == 200

        # Verify the existing RSS is still there (wasn't affected)
        remaining = engine.rss.search_all()
        assert len(remaining) == 1
        assert remaining[0].id == 1
