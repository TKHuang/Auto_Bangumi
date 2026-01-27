"""Integration tests for RSS API endpoints.

This module contains integration tests for the RSS API routes:
- /api/v1/rss/add (POST)
- /api/v1/rss/refresh/all (GET)
- /api/v1/rss/refresh/{id} (GET)
- /api/v1/rss/delete/{id} (DELETE)
- /api/v1/rss/delete/many (POST)
- /api/v1/rss/recreate/{id} (POST)
- /api/v1/rss/subscribe (POST)
- /api/v1/rss/subscribe/batch (POST)
"""

from unittest.mock import MagicMock, patch

import pytest

from module.models.bangumi import Bangumi
from module.models.response import ResponseModel
from module.models.rss import RSSItem


class TestRSSAPIAddRSS:
    """Tests for POST /api/v1/rss/add endpoint."""

    @pytest.mark.integration
    def test_add_non_aggregate_rss_success(self, authenticated_client):
        """Test adding a non-aggregate RSS feed via API succeeds."""
        # Mock the RSSAnalyser.link_to_data to return a valid Bangumi
        mock_bangumi = Bangumi(
            official_title="Test Anime",
            title_raw="[TestGroup] Test Anime",
            season=1,
            group_name="TestGroup",
            rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=99999",
        )

        with patch("module.api.rss.RSSAnalyser") as mock_analyser_class:
            mock_analyser = MagicMock()
            mock_analyser.link_to_data.return_value = mock_bangumi
            mock_analyser_class.return_value = mock_analyser

            response = authenticated_client.post(
                "/api/v1/rss/add",
                json={
                    "url": "https://mikanani.me/RSS/Bangumi?bangumiId=99999",
                    "name": "Test Non-Aggregate Feed",
                    "aggregate": False,
                    "parser": "mikan",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data.get("status") is True or "success" in data.get("msg_en", "").lower()

    @pytest.mark.integration
    def test_add_aggregate_rss_success(self, authenticated_client):
        """Test adding an aggregate RSS feed via API succeeds."""
        response = authenticated_client.post(
            "/api/v1/rss/add",
            json={
                "url": "https://mikanani.me/RSS/MyBangumi?token=abc123",
                "name": "Test Aggregate Feed",
                "aggregate": True,
                "parser": "mikan",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data.get("status") is True or "success" in data.get("msg_en", "").lower()

    @pytest.mark.integration
    def test_add_duplicate_url_returns_error(self, authenticated_client):
        """Test adding duplicate RSS URL returns an error response."""
        # First, add an aggregate RSS (simpler, no parsing required)
        response1 = authenticated_client.post(
            "/api/v1/rss/add",
            json={
                "url": "https://mikanani.me/RSS/MyBangumi?token=duplicate",
                "name": "First Feed",
                "aggregate": True,
                "parser": "mikan",
            },
        )
        assert response1.status_code == 200

        # Try to add the same URL again
        response2 = authenticated_client.post(
            "/api/v1/rss/add",
            json={
                "url": "https://mikanani.me/RSS/MyBangumi?token=duplicate",
                "name": "Second Feed",
                "aggregate": True,
                "parser": "mikan",
            },
        )

        # Should fail with error status code (406 for duplicate URL, 409 for duplicate bangumi)
        # or status=False in the response body
        data = response2.json()
        if response2.status_code == 200:
            # If 200, check for status=False in response
            assert data.get("status") is False
        else:
            # Error status codes: 406 (duplicate URL) or 409 (duplicate bangumi)
            assert response2.status_code in [406, 409]


class TestRSSAPIRefresh:
    """Tests for RSS refresh endpoints."""

    @pytest.mark.integration
    def test_refresh_all_rss_success(self, authenticated_client):
        """Test GET /api/v1/rss/refresh/all returns success.

        This test calls refresh/all with an empty database, which should
        still succeed (just no RSS to refresh).
        """
        response = authenticated_client.get("/api/v1/rss/refresh/all")

        assert response.status_code == 200
        data = response.json()
        assert "success" in data.get("msg_en", "").lower()

    @pytest.mark.integration
    def test_refresh_single_rss_by_id(self, authenticated_client):
        """Test GET /api/v1/rss/refresh/{id} returns success.

        First adds an aggregate RSS (which doesn't require parsing),
        then refreshes it.
        """
        # Add an aggregate RSS feed to refresh
        add_response = authenticated_client.post(
            "/api/v1/rss/add",
            json={
                "url": "https://mikanani.me/RSS/MyBangumi?token=refresh_single",
                "name": "Refresh Single Test Feed",
                "aggregate": True,
                "parser": "mikan",
            },
        )
        assert add_response.status_code == 200

        # Get the RSS list to find the ID
        rss_response = authenticated_client.get("/api/v1/rss")
        rss_list = rss_response.json()
        assert len(rss_list) > 0
        rss_id = rss_list[0]["id"]

        # Refresh single RSS by ID
        response = authenticated_client.get(f"/api/v1/rss/refresh/{rss_id}")

        assert response.status_code == 200
        data = response.json()
        assert "success" in data.get("msg_en", "").lower()


class TestRSSAPIDelete:
    """Tests for RSS delete endpoints."""

    @pytest.mark.integration
    def test_delete_single_rss_by_id(self, authenticated_client):
        """Test DELETE /api/v1/rss/delete/{id} removes RSS."""
        # First add an RSS feed to delete
        authenticated_client.post(
            "/api/v1/rss/add",
            json={
                "url": "https://mikanani.me/RSS/MyBangumi?token=delete_single",
                "name": "Delete Single Test Feed",
                "aggregate": True,
                "parser": "mikan",
            },
        )

        # Get the RSS list to find the ID
        rss_response = authenticated_client.get("/api/v1/rss")
        rss_list = rss_response.json()
        assert len(rss_list) > 0
        rss_id = rss_list[0]["id"]

        # Delete the RSS
        response = authenticated_client.delete(f"/api/v1/rss/delete/{rss_id}")

        assert response.status_code == 200
        data = response.json()
        assert "success" in data.get("msg_en", "").lower()

        # Verify deletion
        verify_response = authenticated_client.get("/api/v1/rss")
        remaining_rss = verify_response.json()
        assert all(r["id"] != rss_id for r in remaining_rss)

    @pytest.mark.integration
    def test_delete_many_rss_batch(self, authenticated_client):
        """Test POST /api/v1/rss/delete/many removes multiple RSS feeds."""
        # Add two RSS feeds to delete
        authenticated_client.post(
            "/api/v1/rss/add",
            json={
                "url": "https://mikanani.me/RSS/MyBangumi?token=delete_many_1",
                "name": "Delete Many Test Feed 1",
                "aggregate": True,
                "parser": "mikan",
            },
        )
        authenticated_client.post(
            "/api/v1/rss/add",
            json={
                "url": "https://mikanani.me/RSS/MyBangumi?token=delete_many_2",
                "name": "Delete Many Test Feed 2",
                "aggregate": True,
                "parser": "mikan",
            },
        )

        # Get the RSS list to find the IDs
        rss_response = authenticated_client.get("/api/v1/rss")
        rss_list = rss_response.json()
        assert len(rss_list) >= 2
        rss_ids = [r["id"] for r in rss_list[:2]]

        # Delete multiple RSS feeds
        response = authenticated_client.post(
            "/api/v1/rss/delete/many",
            json=rss_ids,
        )

        assert response.status_code == 200
        data = response.json()
        # Response may have status=True or msg_en containing "success"
        assert data.get("status") is True or "success" in data.get("msg_en", "").lower()

        # Verify deletion
        verify_response = authenticated_client.get("/api/v1/rss")
        remaining_rss = verify_response.json()
        for rss_id in rss_ids:
            assert all(r["id"] != rss_id for r in remaining_rss)


class TestRSSAPIRecreate:
    """Tests for POST /api/v1/rss/recreate/{id} endpoint."""

    @pytest.mark.integration
    def test_recreate_aggregate_rss_returns_bangumi_list(self, authenticated_client):
        """Test POST /api/v1/rss/recreate/{id} for aggregate RSS returns bangumi list.

        For aggregate RSS, recreate should parse ALL torrents and return multiple
        Bangumi rules for user review.
        """
        # First, add an aggregate RSS feed
        add_response = authenticated_client.post(
            "/api/v1/rss/add",
            json={
                "url": "https://mikanani.me/RSS/MyBangumi?token=recreate_agg",
                "name": "Recreate Aggregate Test Feed",
                "aggregate": True,
                "parser": "mikan",
            },
        )
        assert add_response.status_code == 200

        # Get the RSS ID
        rss_response = authenticated_client.get("/api/v1/rss")
        rss_list = rss_response.json()
        assert len(rss_list) > 0
        rss_id = rss_list[0]["id"]

        # Mock RSSAnalyser to return sample bangumi list for aggregate RSS
        with patch("module.api.rss.RSSAnalyser") as mock_analyser_class:
            mock_analyser = MagicMock()
            # Mock get_rss_torrents to return sample torrents
            mock_analyser.get_rss_torrents.return_value = [
                {
                    "name": "[Group] Anime 1 - 01 [1080p]",
                    "link": "https://example.com/1.torrent",
                },
                {
                    "name": "[Group] Anime 2 - 01 [1080p]",
                    "link": "https://example.com/2.torrent",
                },
            ]
            # Mock torrents_to_data to return bangumi list
            mock_bangumi1 = Bangumi(
                official_title="Anime 1",
                title_raw="[Group] Anime 1",
                season=1,
                group_name="Group",
                rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=11111",
            )
            mock_bangumi2 = Bangumi(
                official_title="Anime 2",
                title_raw="[Group] Anime 2",
                season=1,
                group_name="Group",
                rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=22222",
            )
            mock_analyser.torrents_to_data.return_value = [mock_bangumi1, mock_bangumi2]
            mock_analyser_class.return_value = mock_analyser

            # Call recreate endpoint
            response = authenticated_client.post(f"/api/v1/rss/recreate/{rss_id}")

        # For aggregate RSS, should return list of Bangumi
        assert response.status_code == 200
        data = response.json()
        # Response is list of Bangumi objects
        assert isinstance(data, list)
        assert len(data) >= 1

    @pytest.mark.integration
    def test_recreate_non_aggregate_rss_returns_single_bangumi(
        self, authenticated_client
    ):
        """Test POST /api/v1/rss/recreate/{id} for non-aggregate RSS returns single bangumi.

        For non-aggregate RSS, recreate should parse only the first torrent and
        return a single Bangumi rule.
        """
        # Mock RSSAnalyser for adding non-aggregate RSS
        mock_bangumi = Bangumi(
            official_title="Test Non-Agg Anime",
            title_raw="[TestGroup] Test Non-Agg Anime",
            season=1,
            group_name="TestGroup",
            rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=77777",
        )

        with patch("module.api.rss.RSSAnalyser") as mock_analyser_class:
            mock_analyser = MagicMock()
            mock_analyser.link_to_data.return_value = mock_bangumi
            mock_analyser_class.return_value = mock_analyser

            # Add a non-aggregate RSS feed
            add_response = authenticated_client.post(
                "/api/v1/rss/add",
                json={
                    "url": "https://mikanani.me/RSS/Bangumi?bangumiId=77777",
                    "name": "Recreate Non-Aggregate Test Feed",
                    "aggregate": False,
                    "parser": "mikan",
                },
            )
            assert add_response.status_code == 200

        # Get the RSS ID (should be the non-aggregate one we just added)
        rss_response = authenticated_client.get("/api/v1/rss")
        rss_list = rss_response.json()
        non_agg_rss = next((r for r in rss_list if not r.get("aggregate", True)), None)
        assert non_agg_rss is not None
        rss_id = non_agg_rss["id"]

        # Mock RSSAnalyser for recreate call
        recreate_bangumi = Bangumi(
            official_title="Recreated Non-Agg Anime",
            title_raw="[TestGroup] Recreated Non-Agg Anime",
            season=1,
            group_name="TestGroup",
            rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=77777",
        )

        with patch("module.api.rss.RSSAnalyser") as mock_analyser_class:
            mock_analyser = MagicMock()
            mock_analyser.link_to_data.return_value = recreate_bangumi
            mock_analyser_class.return_value = mock_analyser

            # Call recreate endpoint
            response = authenticated_client.post(f"/api/v1/rss/recreate/{rss_id}")

        # For non-aggregate RSS, should return list with single Bangumi
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        # Verify the returned bangumi has expected structure
        assert "official_title" in data[0] or "title_raw" in data[0]


class TestRSSAPISubscribe:
    """Tests for POST /api/v1/rss/subscribe and /api/v1/rss/subscribe/batch endpoints."""

    @pytest.mark.integration
    def test_subscribe_single_bangumi_success(self, authenticated_client):
        """Test POST /api/v1/rss/subscribe creates a single bangumi subscription.

        This endpoint takes a Bangumi object and an RSSItem, and creates
        the subscription by calling SeasonCollector.subscribe_season.
        """
        # First, add an RSS feed (aggregate since it's simpler)
        add_response = authenticated_client.post(
            "/api/v1/rss/add",
            json={
                "url": "https://mikanani.me/RSS/MyBangumi?token=subscribe_single",
                "name": "Subscribe Single Test Feed",
                "aggregate": True,
                "parser": "mikan",
            },
        )
        assert add_response.status_code == 200

        # Get the RSS to use for subscribe
        rss_response = authenticated_client.get("/api/v1/rss")
        rss_list = rss_response.json()
        assert len(rss_list) > 0
        rss_item = rss_list[0]

        # Prepare bangumi data to subscribe
        bangumi_data = {
            "official_title": "Subscribe Test Anime",
            "title_raw": "[SubGroup] Subscribe Test Anime",
            "season": 1,
            "group_name": "SubGroup",
            "rss_link": "https://mikanani.me/RSS/Bangumi?bangumiId=88888",
            "rss_id": rss_item["id"],
        }

        # Mock SeasonCollector.subscribe_season to avoid actual processing
        with patch("module.api.rss.SeasonCollector") as mock_collector_class:
            mock_collector = MagicMock()
            mock_collector.subscribe_season.return_value = ResponseModel(
                status=True,
                status_code=200,
                msg_en="Subscription successful.",
                msg_zh="订阅成功。",
            )
            mock_collector.__enter__.return_value = mock_collector
            mock_collector.__exit__.return_value = None
            mock_collector_class.return_value = mock_collector

            # Call subscribe endpoint
            response = authenticated_client.post(
                "/api/v1/rss/subscribe",
                json={
                    "data": bangumi_data,
                    "rss": rss_item,
                },
            )

        # Check response - endpoint uses u_response wrapper which transforms ResponseModel
        assert response.status_code == 200
        data = response.json()
        # Response should indicate success
        assert "success" in data.get("msg_en", "").lower()

    @pytest.mark.integration
    def test_subscribe_batch_multiple_bangumi_success(self, authenticated_client):
        """Test POST /api/v1/rss/subscribe/batch creates multiple bangumi subscriptions.

        This endpoint takes a list of Bangumi objects and an RSSItem, and creates
        all subscriptions in a single transaction via SeasonCollector.subscribe_batch.
        """
        # First, add an aggregate RSS feed
        add_response = authenticated_client.post(
            "/api/v1/rss/add",
            json={
                "url": "https://mikanani.me/RSS/MyBangumi?token=subscribe_batch",
                "name": "Subscribe Batch Test Feed",
                "aggregate": True,
                "parser": "mikan",
            },
        )
        assert add_response.status_code == 200

        # Get the RSS to use for batch subscribe
        rss_response = authenticated_client.get("/api/v1/rss")
        rss_list = rss_response.json()
        assert len(rss_list) > 0
        rss_item = rss_list[0]

        # Prepare multiple bangumi to subscribe
        bangumi_list = [
            {
                "official_title": "Batch Anime 1",
                "title_raw": "[BatchGroup] Batch Anime 1",
                "season": 1,
                "group_name": "BatchGroup",
                "rss_link": "https://mikanani.me/RSS/Bangumi?bangumiId=91111",
            },
            {
                "official_title": "Batch Anime 2",
                "title_raw": "[BatchGroup] Batch Anime 2",
                "season": 1,
                "group_name": "BatchGroup",
                "rss_link": "https://mikanani.me/RSS/Bangumi?bangumiId=92222",
            },
        ]

        # Mock SeasonCollector.subscribe_batch to avoid actual processing
        with patch("module.api.rss.SeasonCollector") as mock_collector_class:
            mock_collector = MagicMock()
            mock_collector.subscribe_batch.return_value = ResponseModel(
                status=True,
                status_code=200,
                msg_en="Batch subscription successful. 2/2 succeeded.",
                msg_zh="批量订阅成功。2/2 成功。",
            )
            mock_collector.__enter__.return_value = mock_collector
            mock_collector.__exit__.return_value = None
            mock_collector_class.return_value = mock_collector

            # Call batch subscribe endpoint
            response = authenticated_client.post(
                "/api/v1/rss/subscribe/batch",
                json={
                    "bangumi_list": bangumi_list,
                    "rss": rss_item,
                },
            )

        # Check response
        assert response.status_code == 200
        data = response.json()
        # Response should indicate success
        assert "success" in data.get("msg_en", "").lower()
