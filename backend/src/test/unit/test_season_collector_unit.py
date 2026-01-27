"""Unit tests for SeasonCollector.

This module contains unit tests for the SeasonCollector class methods.
"""

from unittest.mock import MagicMock, patch

import pytest

from module.models.bangumi import Bangumi
from module.models.rss import RSSItem


class TestSeasonCollectorSubscribeSeason:
    """Tests for SeasonCollector.subscribe_season method."""

    @pytest.mark.unit
    def test_subscribe_creates_rss_if_not_exists(
        self, in_memory_engine, mock_download_client
    ):
        """Test that subscribe_season creates RSS if it doesn't exist.

        When subscribing to a bangumi without an existing RSS feed,
        the method should create a new RSS entry and link the bangumi to it.
        """
        from module.rss import RSSEngine

        # Set up database with tables but no RSS
        engine = RSSEngine(_engine=in_memory_engine)
        engine.create_table()

        # Verify no RSS exists initially
        assert len(engine.rss.search_all()) == 0

        # Create bangumi data without rss_id (will trigger RSS creation)
        bangumi_data = Bangumi(
            official_title="New Anime",
            title_raw="[TestGroup] New Anime",
            season=1,
            group_name="TestGroup",
            rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=99999",
        )

        # Mock RSSEngine context manager and its methods
        mock_engine = MagicMock()
        mock_rss_db = MagicMock()
        mock_bangumi_db = MagicMock()

        # Configure mock engine
        mock_engine.rss = mock_rss_db
        mock_engine.bangumi = mock_bangumi_db
        mock_engine.__enter__ = MagicMock(return_value=mock_engine)
        mock_engine.__exit__ = MagicMock(return_value=None)

        # Initially no RSS with this URL
        mock_rss_db.search_all.return_value = []
        # After add_rss, search returns the new RSS
        new_rss = RSSItem(
            id=1,
            name="New Anime",
            url="https://mikanani.me/RSS/Bangumi?bangumiId=99999",
            aggregate=False,
        )

        # Track add_rss calls to update search_all return value
        def update_after_add_rss(*args, **kwargs):
            mock_rss_db.search_all.return_value = [new_rss]

        mock_engine.add_rss.side_effect = update_after_add_rss

        # No duplicate bangumi exists
        mock_bangumi_db.search_by_composite_key.return_value = None
        mock_bangumi_db.get_all_by_rss_id.return_value = []

        # Download returns success
        mock_engine.download_bangumi.return_value = MagicMock(status=True)

        with patch(
            "module.manager.collector.RSSEngine",
            return_value=mock_engine,
        ):
            from module.manager.collector import SeasonCollector

            SeasonCollector.subscribe_season(bangumi_data, parser="mikan")

        # Verify add_rss was called to create the RSS feed
        mock_engine.add_rss.assert_called_once()
        call_kwargs = mock_engine.add_rss.call_args
        assert call_kwargs.kwargs["rss_link"] == bangumi_data.rss_link
        assert call_kwargs.kwargs["aggregate"] is False
        assert call_kwargs.kwargs["parser"] == "mikan"

        # Verify bangumi was added
        mock_bangumi_db.add.assert_called_once()

        # Verify commit was called
        mock_engine.commit.assert_called_once()

    @pytest.mark.unit
    def test_subscribe_deletes_existing_bangumi_first(
        self, in_memory_engine, mock_download_client
    ):
        """Test that subscribe_season deletes existing bangumi from same RSS first.

        For non-aggregate RSS (single bangumi), the method should delete any
        existing bangumi from that RSS before inserting the new one.
        """
        # Create mock for RSSEngine
        mock_engine = MagicMock()
        mock_rss_db = MagicMock()
        mock_bangumi_db = MagicMock()

        mock_engine.rss = mock_rss_db
        mock_engine.bangumi = mock_bangumi_db
        mock_engine.__enter__ = MagicMock(return_value=mock_engine)
        mock_engine.__exit__ = MagicMock(return_value=None)

        # RSS already exists
        existing_rss = RSSItem(
            id=5,
            name="Existing Feed",
            url="https://mikanani.me/RSS/Bangumi?bangumiId=12345",
            aggregate=False,
        )
        mock_rss_db.search_all.return_value = [existing_rss]

        # Existing bangumi from this RSS
        existing_bangumi = Bangumi(
            id=10,
            rss_id=5,
            official_title="Old Anime",
            title_raw="[OldGroup] Old Anime",
            season=1,
            group_name="OldGroup",
            rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=12345",
        )
        mock_bangumi_db.get_all_by_rss_id.return_value = [existing_bangumi]

        # No duplicate from different RSS
        mock_bangumi_db.search_by_composite_key.return_value = None

        # Download returns success
        mock_engine.download_bangumi.return_value = MagicMock(status=True)

        # New bangumi data (without rss_id, will find existing RSS)
        new_bangumi_data = Bangumi(
            official_title="New Anime",
            title_raw="[TestGroup] New Anime",
            season=1,
            group_name="TestGroup",
            rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=12345",
        )

        with patch(
            "module.manager.collector.RSSEngine",
            return_value=mock_engine,
        ):
            from module.manager.collector import SeasonCollector

            SeasonCollector.subscribe_season(new_bangumi_data)

        # Verify existing bangumi was deleted before adding new one
        mock_bangumi_db.delete_all_by_rss_id.assert_called_once_with(5)

        # Verify new bangumi was added
        mock_bangumi_db.add.assert_called_once()

        # Verify commit was called
        mock_engine.commit.assert_called_once()

    @pytest.mark.unit
    def test_subscribe_fails_for_duplicate_from_different_rss(
        self, in_memory_engine, mock_download_client
    ):
        """Test that subscribe_season fails when bangumi exists from different RSS.

        If the same bangumi (same official_title + season + group) is already
        subscribed from a different RSS source, the method should raise an error.
        """
        # Create mock for RSSEngine
        mock_engine = MagicMock()
        mock_rss_db = MagicMock()
        mock_bangumi_db = MagicMock()

        mock_engine.rss = mock_rss_db
        mock_engine.bangumi = mock_bangumi_db
        mock_engine.__enter__ = MagicMock(return_value=mock_engine)
        mock_engine.__exit__ = MagicMock(return_value=None)

        # New RSS that doesn't exist yet (will be created)
        new_rss = RSSItem(
            id=2,
            name="New Feed",
            url="https://mikanani.me/RSS/Bangumi?bangumiId=99999",
            aggregate=False,
        )

        # Initially no RSS, then after creation has new RSS
        call_count = [0]

        def search_all_side_effect():
            call_count[0] += 1
            if call_count[0] <= 1:
                return []  # First call: no RSS
            return [new_rss]  # After add_rss: has RSS

        mock_rss_db.search_all.side_effect = search_all_side_effect

        # Existing bangumi from DIFFERENT RSS (id=100, not id=2)
        existing_bangumi = Bangumi(
            id=50,
            rss_id=100,  # Different RSS ID
            official_title="Same Anime",
            title_raw="[TestGroup] Same Anime",
            season=1,
            group_name="TestGroup",
            rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=11111",
        )

        # Return existing bangumi when checking for duplicates
        mock_bangumi_db.search_by_composite_key.return_value = existing_bangumi

        # Return the other RSS info
        other_rss = RSSItem(
            id=100,
            name="Other Feed",
            url="https://mikanani.me/RSS/Bangumi?bangumiId=11111",
            aggregate=False,
        )
        mock_rss_db.search_id.return_value = other_rss

        # New bangumi data that conflicts with existing
        conflicting_bangumi = Bangumi(
            official_title="Same Anime",
            title_raw="[TestGroup] Same Anime",
            season=1,
            group_name="TestGroup",
            rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=99999",
        )

        with patch(
            "module.manager.collector.RSSEngine",
            return_value=mock_engine,
        ):
            from module.manager.collector import SeasonCollector

            # Should raise ValueError due to duplicate from different RSS
            with pytest.raises(ValueError) as exc_info:
                SeasonCollector.subscribe_season(conflicting_bangumi)

            # Verify error message mentions the conflict
            error_msg = str(exc_info.value)
            assert "already subscribed" in error_msg.lower()
            assert "100" in error_msg  # Should mention the existing RSS ID

        # Verify rollback was called after the exception
        mock_engine.rollback.assert_called_once()

        # Verify bangumi was NOT added
        mock_bangumi_db.add.assert_not_called()


class TestSeasonCollectorSubscribeBatch:
    """Tests for SeasonCollector.subscribe_batch method."""

    @pytest.mark.unit
    def test_deletes_all_existing_once_not_per_item(
        self, in_memory_engine, mock_download_client
    ):
        """Test that subscribe_batch deletes all existing bangumi once, not per item.

        When batch subscribing multiple bangumi for an RSS ID, the method should
        delete all existing bangumi from that RSS ONCE at the start, not for
        each individual bangumi in the list.
        """
        # Create mock for RSSEngine
        mock_engine = MagicMock()
        mock_rss_db = MagicMock()
        mock_bangumi_db = MagicMock()

        mock_engine.rss = mock_rss_db
        mock_engine.bangumi = mock_bangumi_db
        mock_engine.__enter__ = MagicMock(return_value=mock_engine)
        mock_engine.__exit__ = MagicMock(return_value=None)

        # Existing bangumi from this RSS (will be deleted once)
        existing_bangumi_list = [
            Bangumi(
                id=10,
                rss_id=5,
                official_title="Old Anime 1",
                title_raw="[OldGroup] Old Anime 1",
                season=1,
                group_name="OldGroup",
            ),
            Bangumi(
                id=11,
                rss_id=5,
                official_title="Old Anime 2",
                title_raw="[OldGroup] Old Anime 2",
                season=1,
                group_name="OldGroup",
            ),
        ]
        mock_bangumi_db.get_all_by_rss_id.return_value = existing_bangumi_list
        mock_bangumi_db.delete_all_by_rss_id.return_value = 2

        # Download returns success
        mock_engine.download_bangumi.return_value = MagicMock(status=True)

        # New bangumi list (3 items)
        new_bangumi_list = [
            Bangumi(
                official_title="New Anime 1",
                title_raw="[TestGroup] New Anime 1",
                season=1,
                group_name="TestGroup",
            ),
            Bangumi(
                official_title="New Anime 2",
                title_raw="[TestGroup] New Anime 2",
                season=1,
                group_name="TestGroup",
            ),
            Bangumi(
                official_title="New Anime 3",
                title_raw="[TestGroup] New Anime 3",
                season=1,
                group_name="TestGroup",
            ),
        ]

        with patch(
            "module.manager.collector.RSSEngine",
            return_value=mock_engine,
        ):
            from module.manager.collector import SeasonCollector

            result = SeasonCollector.subscribe_batch(
                bangumi_list=new_bangumi_list, rss_id=5, parser="mikan"
            )

        # Verify delete_all_by_rss_id was called EXACTLY ONCE (not 3 times for 3 items)
        mock_bangumi_db.delete_all_by_rss_id.assert_called_once_with(5)

        # Verify all 3 new bangumi were added
        assert mock_bangumi_db.add.call_count == 3

        # Verify commit was called once for all inserts
        mock_engine.commit.assert_called_once()

        # Verify result indicates success
        assert result.status is True
        assert result.status_code == 200

    @pytest.mark.unit
    def test_empty_list_returns_error(self, in_memory_engine, mock_download_client):
        """Test that subscribe_batch returns error for empty list.

        When provided with an empty bangumi list, the method should return
        a ResponseModel with status=False and appropriate error message.
        """
        # Create mock for RSSEngine
        mock_engine = MagicMock()
        mock_engine.__enter__ = MagicMock(return_value=mock_engine)
        mock_engine.__exit__ = MagicMock(return_value=None)

        with patch(
            "module.manager.collector.RSSEngine",
            return_value=mock_engine,
        ):
            from module.manager.collector import SeasonCollector

            result = SeasonCollector.subscribe_batch(
                bangumi_list=[], rss_id=5, parser="mikan"
            )

        # Verify result indicates error
        assert result.status is False
        assert result.status_code == 400
        assert "no bangumi" in result.msg_en.lower()

        # Verify no database operations were attempted
        mock_engine.bangumi.delete_all_by_rss_id.assert_not_called()
        mock_engine.bangumi.add.assert_not_called()
        mock_engine.commit.assert_not_called()

    @pytest.mark.unit
    def test_partial_failures_reported_correctly(
        self, in_memory_engine, mock_download_client
    ):
        """Test that subscribe_batch correctly reports partial failures.

        When some bangumi insertions fail, the method should report which
        ones failed while still succeeding for the others.
        """
        # Create mock for RSSEngine
        mock_engine = MagicMock()
        mock_rss_db = MagicMock()
        mock_bangumi_db = MagicMock()

        mock_engine.rss = mock_rss_db
        mock_engine.bangumi = mock_bangumi_db
        mock_engine.__enter__ = MagicMock(return_value=mock_engine)
        mock_engine.__exit__ = MagicMock(return_value=None)

        # No existing bangumi to delete
        mock_bangumi_db.get_all_by_rss_id.return_value = []

        # Configure add to fail on the second item
        call_count = [0]

        def add_side_effect(bangumi):
            call_count[0] += 1
            if call_count[0] == 2:
                raise Exception("Database constraint error")
            return True

        mock_bangumi_db.add.side_effect = add_side_effect

        # Download returns success
        mock_engine.download_bangumi.return_value = MagicMock(status=True)

        # New bangumi list (3 items, second will fail)
        new_bangumi_list = [
            Bangumi(
                official_title="Success Anime 1",
                title_raw="[TestGroup] Success Anime 1",
                season=1,
                group_name="TestGroup",
            ),
            Bangumi(
                official_title="Failing Anime",
                title_raw="[TestGroup] Failing Anime",
                season=1,
                group_name="TestGroup",
            ),
            Bangumi(
                official_title="Success Anime 2",
                title_raw="[TestGroup] Success Anime 2",
                season=1,
                group_name="TestGroup",
            ),
        ]

        with patch(
            "module.manager.collector.RSSEngine",
            return_value=mock_engine,
        ):
            from module.manager.collector import SeasonCollector

            result = SeasonCollector.subscribe_batch(
                bangumi_list=new_bangumi_list, rss_id=5, parser="mikan"
            )

        # Verify result indicates partial success
        assert result.status is True  # Partial success still returns True
        assert result.status_code == 200

        # Verify the failed item is mentioned in the message
        assert "Failing Anime" in result.msg_en
        assert "2/3" in result.msg_en  # 2 out of 3 succeeded

        # Verify commit was still called (for the successful items)
        mock_engine.commit.assert_called_once()

        # Verify all 3 items were attempted
        assert mock_bangumi_db.add.call_count == 3
