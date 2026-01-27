"""Integration tests for Bangumi API endpoints.

This module contains integration tests for the Bangumi API routes:
- /api/v1/bangumi/get/all (GET)
- /api/v1/bangumi/delete/{id} (DELETE)
- /api/v1/bangumi/delete (DELETE batch)
- /api/v1/bangumi/disable/{id} (DELETE)
- /api/v1/bangumi/enable/{id} (GET)
- /api/v1/bangumi/torrent/{id} (GET)
- /api/v1/bangumi/torrent/download (POST)
"""

from unittest.mock import MagicMock, patch

import pytest

from module.models.bangumi import Bangumi
from module.models.response import ResponseModel


class TestBangumiAPIGet:
    """Tests for GET /api/v1/bangumi/get/all endpoint."""

    @pytest.mark.integration
    def test_get_all_bangumi_returns_list(self, authenticated_client):
        """Test GET /api/v1/bangumi/get/all returns list of all bangumi.

        This test:
        1. First adds an RSS feed via the API (to create proper database entries)
        2. Calls the GET /api/v1/bangumi/get/all endpoint
        3. Verifies the response is a list
        """
        # First, add a non-aggregate RSS which will create a bangumi
        mock_bangumi = Bangumi(
            official_title="Test Anime GET",
            title_raw="[TestGroup] Test Anime GET",
            season=1,
            group_name="TestGroup",
            rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=getall",
        )

        with patch("module.api.rss.RSSAnalyser") as mock_analyser_class:
            mock_analyser = MagicMock()
            mock_analyser.link_to_data.return_value = mock_bangumi
            mock_analyser_class.return_value = mock_analyser

            add_response = authenticated_client.post(
                "/api/v1/rss/add",
                json={
                    "url": "https://mikanani.me/RSS/Bangumi?bangumiId=getall",
                    "name": "Test GET All Feed",
                    "aggregate": False,
                    "parser": "mikan",
                },
            )
            assert add_response.status_code == 200

        # Now get all bangumi
        response = authenticated_client.get("/api/v1/bangumi/get/all")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestBangumiAPIDelete:
    """Tests for DELETE /api/v1/bangumi/delete endpoints."""

    @pytest.mark.integration
    def test_delete_single_bangumi_by_id(self, authenticated_client):
        """Test DELETE /api/v1/bangumi/delete/{id} removes a single bangumi.

        This test:
        1. Adds a non-aggregate RSS (creates bangumi)
        2. Gets the bangumi list to find the ID
        3. Deletes the bangumi via the API
        4. Verifies the response indicates success
        """
        # First, add a non-aggregate RSS which will create a bangumi
        mock_bangumi = Bangumi(
            official_title="Delete Test Anime",
            title_raw="[TestGroup] Delete Test Anime",
            season=1,
            group_name="TestGroup",
            rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=delete1",
        )

        with patch("module.api.rss.RSSAnalyser") as mock_analyser_class:
            mock_analyser = MagicMock()
            mock_analyser.link_to_data.return_value = mock_bangumi
            mock_analyser_class.return_value = mock_analyser

            add_response = authenticated_client.post(
                "/api/v1/rss/add",
                json={
                    "url": "https://mikanani.me/RSS/Bangumi?bangumiId=delete1",
                    "name": "Delete Test Feed",
                    "aggregate": False,
                    "parser": "mikan",
                },
            )
            assert add_response.status_code == 200

        # Get the bangumi list to find the ID
        bangumi_response = authenticated_client.get("/api/v1/bangumi/get/all")
        bangumi_list = bangumi_response.json()

        assert len(bangumi_list) >= 1
        bangumi_id = bangumi_list[0]["id"]

        # Delete the bangumi
        response = authenticated_client.delete(f"/api/v1/bangumi/delete/{bangumi_id}")

        assert response.status_code == 200
        data = response.json()
        # Response contains "Delete rule for <title>" message
        assert "delete" in data.get("msg_en", "").lower() or data.get("status") is True

    @pytest.mark.integration
    def test_delete_batch_bangumi(self, authenticated_client):
        """Test DELETE /api/v1/bangumi/delete removes multiple bangumi.

        This test:
        1. Adds multiple RSS feeds (creates bangumi)
        2. Gets bangumi IDs
        3. Deletes them via batch API
        4. Verifies success
        """
        # Add first RSS/bangumi
        mock_bangumi1 = Bangumi(
            official_title="Batch Delete Anime 1",
            title_raw="[TestGroup] Batch Delete Anime 1",
            season=1,
            group_name="TestGroup",
            rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=batch1",
        )

        with patch("module.api.rss.RSSAnalyser") as mock_analyser_class:
            mock_analyser = MagicMock()
            mock_analyser.link_to_data.return_value = mock_bangumi1
            mock_analyser_class.return_value = mock_analyser

            authenticated_client.post(
                "/api/v1/rss/add",
                json={
                    "url": "https://mikanani.me/RSS/Bangumi?bangumiId=batch1",
                    "name": "Batch Delete Feed 1",
                    "aggregate": False,
                    "parser": "mikan",
                },
            )

        # Add second RSS/bangumi
        mock_bangumi2 = Bangumi(
            official_title="Batch Delete Anime 2",
            title_raw="[TestGroup] Batch Delete Anime 2",
            season=1,
            group_name="TestGroup",
            rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=batch2",
        )

        with patch("module.api.rss.RSSAnalyser") as mock_analyser_class:
            mock_analyser = MagicMock()
            mock_analyser.link_to_data.return_value = mock_bangumi2
            mock_analyser_class.return_value = mock_analyser

            authenticated_client.post(
                "/api/v1/rss/add",
                json={
                    "url": "https://mikanani.me/RSS/Bangumi?bangumiId=batch2",
                    "name": "Batch Delete Feed 2",
                    "aggregate": False,
                    "parser": "mikan",
                },
            )

        # Get bangumi IDs
        bangumi_response = authenticated_client.get("/api/v1/bangumi/get/all")
        bangumi_list = bangumi_response.json()

        assert len(bangumi_list) >= 2
        bangumi_ids = [b["id"] for b in bangumi_list[:2]]

        # Delete batch
        response = authenticated_client.request(
            "DELETE",
            "/api/v1/bangumi/delete",
            json=bangumi_ids,
        )

        assert response.status_code == 200
        data = response.json()
        # Response contains "Deleted X rules" message
        assert "delete" in data.get("msg_en", "").lower() or data.get("status") is True

    @pytest.mark.integration
    def test_disable_enable_toggle_bangumi(self, authenticated_client):
        """Test disable/enable toggle endpoints for bangumi.

        This test:
        1. Adds a non-aggregate RSS (creates bangumi)
        2. Disables it via DELETE /api/v1/bangumi/disable/{id}
        3. Enables it via GET /api/v1/bangumi/enable/{id}
        """
        # Add RSS/bangumi
        mock_bangumi = Bangumi(
            official_title="Toggle Test Anime",
            title_raw="[TestGroup] Toggle Test Anime",
            season=1,
            group_name="TestGroup",
            rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=toggle",
        )

        with patch("module.api.rss.RSSAnalyser") as mock_analyser_class:
            mock_analyser = MagicMock()
            mock_analyser.link_to_data.return_value = mock_bangumi
            mock_analyser_class.return_value = mock_analyser

            authenticated_client.post(
                "/api/v1/rss/add",
                json={
                    "url": "https://mikanani.me/RSS/Bangumi?bangumiId=toggle",
                    "name": "Toggle Test Feed",
                    "aggregate": False,
                    "parser": "mikan",
                },
            )

        # Get bangumi ID
        bangumi_response = authenticated_client.get("/api/v1/bangumi/get/all")
        bangumi_list = bangumi_response.json()

        assert len(bangumi_list) >= 1
        bangumi_id = bangumi_list[0]["id"]

        # Disable the bangumi
        disable_response = authenticated_client.delete(
            f"/api/v1/bangumi/disable/{bangumi_id}"
        )
        assert disable_response.status_code == 200
        disable_data = disable_response.json()
        # Response contains "Disable rule for <title>" message
        assert (
            "disable" in disable_data.get("msg_en", "").lower()
            or disable_data.get("status") is True
        )

        # Enable the bangumi
        enable_response = authenticated_client.get(
            f"/api/v1/bangumi/enable/{bangumi_id}"
        )
        assert enable_response.status_code == 200
        enable_data = enable_response.json()
        # Response contains "Enable rule for <title>" message
        assert (
            "enable" in enable_data.get("msg_en", "").lower()
            or enable_data.get("status") is True
        )


class TestBangumiAPITorrent:
    """Tests for bangumi torrent status endpoints."""

    @pytest.mark.integration
    def test_get_torrent_status_by_bangumi_id(self, authenticated_client):
        """Test GET /api/v1/bangumi/torrent/{id} returns torrent status.

        This test:
        1. Adds a non-aggregate RSS (creates bangumi)
        2. Gets the bangumi ID
        3. Calls the torrent status endpoint
        4. Verifies the response is a list (may be empty if no torrents)
        """
        # Add RSS/bangumi
        mock_bangumi = Bangumi(
            official_title="Torrent Status Test Anime",
            title_raw="[TestGroup] Torrent Status Test Anime",
            season=1,
            group_name="TestGroup",
            rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=torrentstatus",
        )

        with patch("module.api.rss.RSSAnalyser") as mock_analyser_class:
            mock_analyser = MagicMock()
            mock_analyser.link_to_data.return_value = mock_bangumi
            mock_analyser_class.return_value = mock_analyser

            authenticated_client.post(
                "/api/v1/rss/add",
                json={
                    "url": "https://mikanani.me/RSS/Bangumi?bangumiId=torrentstatus",
                    "name": "Torrent Status Test Feed",
                    "aggregate": False,
                    "parser": "mikan",
                },
            )

        # Get bangumi ID
        bangumi_response = authenticated_client.get("/api/v1/bangumi/get/all")
        bangumi_list = bangumi_response.json()

        assert len(bangumi_list) >= 1
        bangumi_id = bangumi_list[0]["id"]

        # Get torrent status
        response = authenticated_client.get(f"/api/v1/bangumi/torrent/{bangumi_id}")

        assert response.status_code == 200
        data = response.json()
        # Should return a list (may be empty if no torrents associated)
        assert isinstance(data, list)

    @pytest.mark.integration
    def test_download_torrent_via_api(self, authenticated_client):
        """Test POST /api/v1/bangumi/torrent/download triggers download.

        This test:
        1. Mocks TorrentStatusManager.download_torrent to return success
        2. Calls the download endpoint
        3. Verifies the response indicates success or appropriate error
        """
        # Mock the download_torrent method to return success
        mock_response = ResponseModel(
            status=True,
            status_code=200,
            msg_en="Download started successfully.",
            msg_zh="下载已启动。",
        )

        # For this test, we'll mock TorrentStatusManager directly at API level
        # since we need to return a specific response for a torrent_id
        # that may not exist in the database
        with patch("module.api.bangumi.TorrentStatusManager") as mock_tsm_class:
            mock_tsm = MagicMock()
            mock_tsm.download_torrent.return_value = mock_response
            mock_tsm.__enter__.return_value = mock_tsm
            mock_tsm.__exit__.return_value = None
            mock_tsm_class.return_value = mock_tsm

            response = authenticated_client.post(
                "/api/v1/bangumi/torrent/download",
                params={"torrent_id": 999},  # Use arbitrary ID since we're mocking
            )

        assert response.status_code == 200
        data = response.json()
        # Response should indicate success
        assert (
            "success" in data.get("msg_en", "").lower()
            or data.get("status") is True
            or "download" in data.get("msg_en", "").lower()
        )
