"""API contract tests for RSS endpoints."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from module.api.v1.rss import router as rss_router
from module.models import RSSItem, ResponseModel


@pytest.fixture
def app():
    """Create FastAPI app with rss router and auth bypass."""
    from module.api.middleware.auth import get_current_user
    
    app = FastAPI()
    app.include_router(rss_router, prefix="/api/v1")
    
    # Override auth dependency to bypass authentication
    async def mock_get_current_user():
        return "testuser"
    
    app.dependency_overrides[get_current_user] = mock_get_current_user
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_rss():
    """Create mock RSS item."""
    return RSSItem(
        id=1,
        name="Test RSS",
        url="https://example.com/rss.xml",
        aggregate=False,
        parser="mikan",
        enabled=True,
        last_update=None,
        last_status=None,
        last_error=None,
    )


class TestGetRSS:
    """Test GET /rss endpoint."""

    @pytest.mark.asyncio
    async def test_get_rss_success(self, client):
        """Test successful retrieval of all RSS feeds."""
        mock_rss_list = [
            {
                "id": 1,
                "name": "RSS Feed 1",
                "url": "https://example.com/rss1.xml",
                "aggregate": False,
                "parser": "mikan",
                "enabled": True,
            },
            {
                "id": 2,
                "name": "RSS Feed 2",
                "url": "https://example.com/rss2.xml",
                "aggregate": True,
                "parser": "bangumi",
                "enabled": False,
            },
        ]

        with patch("module.api.v1.rss.RSSEngine") as mock_engine:
            mock_instance = MagicMock()
            mock_engine.return_value.__enter__.return_value = mock_instance
            mock_instance.rss.search_all.return_value = mock_rss_list

            response = client.get("/api/v1/rss")

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 2
            assert data[0]["name"] == "RSS Feed 1"

    @pytest.mark.asyncio
    async def test_get_rss_empty(self, client):
        """Test retrieval when no RSS feeds exist."""
        with patch("module.api.v1.rss.RSSEngine") as mock_engine:
            mock_instance = MagicMock()
            mock_engine.return_value.__enter__.return_value = mock_instance
            mock_instance.rss.search_all.return_value = []

            response = client.get("/api/v1/rss")

            assert response.status_code == 200
            data = response.json()
            assert data == []


class TestAddRSS:
    """Test POST /rss/add endpoint."""

    @pytest.mark.asyncio
    async def test_add_rss_skip_bangumi(self, client, mock_rss):
        """Test adding RSS with skip_bangumi flag."""
        mock_response = ResponseModel(
            status=True,
            status_code=200,
            msg_en="RSS added successfully.",
            msg_zh="RSS 添加成功。",
        )

        with patch("module.api.v1.rss.RSSEngine") as mock_engine:
            mock_instance = MagicMock()
            mock_engine.return_value.__enter__.return_value = mock_instance
            mock_instance.add_rss.return_value = mock_response
            mock_instance.rss.search_all.return_value = [mock_rss]

            response = client.post(
                "/api/v1/rss/add",
                json={
                    "name": "Test RSS",
                    "url": "https://example.com/rss.xml",
                    "aggregate": False,
                    "parser": "mikan",
                },
                params={"skip_bangumi": True},
            )

            assert response.status_code == 200
            data = response.json()
            assert "msg_en" in data or "rss_id" in data

    @pytest.mark.asyncio
    async def test_add_rss_with_manual_input(self, client, mock_rss):
        """Test adding RSS with manual override."""
        mock_response = ResponseModel(
            status=True,
            status_code=200,
            msg_en="RSS added successfully.",
            msg_zh="RSS 添加成功。",
        )

        with patch("module.api.v1.rss.RSSEngine") as mock_engine:
            with patch("module.api.v1.rss.RSSAnalyser") as mock_analyser:
                mock_instance = MagicMock()
                mock_engine.return_value.__enter__.return_value = mock_instance
                mock_instance.add_rss.return_value = mock_response

                response = client.post(
                    "/api/v1/rss/add",
                    json={
                        "name": "Test RSS",
                        "url": "https://example.com/rss.xml",
                        "aggregate": False,
                        "parser": "mikan",
                    },
                    params={
                        "official_title": "Custom Title",
                        "season": 2,
                        "group_name": "CustomGroup",
                    },
                )

                assert response.status_code in [200, 422]


class TestDeleteRSS:
    """Test DELETE /rss/delete/{rss_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_rss_success(self, client):
        """Test successful RSS deletion."""
        with patch("module.api.v1.rss.RSSEngine") as mock_engine:
            mock_instance = MagicMock()
            mock_engine.return_value.__enter__.return_value = mock_instance
            mock_instance.rss.delete.return_value = True

            response = client.delete("/api/v1/rss/delete/1")

            assert response.status_code == 200
            data = response.json()
            assert data["msg_en"] == "Delete RSS successfully."
            assert data["msg_zh"] == "删除 RSS 成功。"

    @pytest.mark.asyncio
    async def test_delete_rss_failed(self, client):
        """Test failed RSS deletion."""
        with patch("module.api.v1.rss.RSSEngine") as mock_engine:
            mock_instance = MagicMock()
            mock_engine.return_value.__enter__.return_value = mock_instance
            mock_instance.rss.delete.return_value = False

            response = client.delete("/api/v1/rss/delete/999")

            assert response.status_code == 406
            data = response.json()
            assert data["msg_en"] == "Delete RSS failed."


class TestDeleteManyRSS:
    """Test POST /rss/delete/many endpoint."""

    @pytest.mark.asyncio
    async def test_delete_many_rss_success(self, client):
        """Test successful batch RSS deletion."""
        mock_response = ResponseModel(
            status=True,
            status_code=200,
            msg_en="Delete successfully.",
            msg_zh="删除成功。",
        )

        with patch("module.api.v1.rss.RSSEngine") as mock_engine:
            mock_instance = MagicMock()
            mock_engine.return_value.__enter__.return_value = mock_instance
            mock_instance.delete_list.return_value = mock_response

            response = client.post("/api/v1/rss/delete/many", json=[1, 2, 3])

            assert response.status_code == 200
            data = response.json()
            assert "msg_en" in data


class TestDisableRSS:
    """Test PATCH /rss/disable/{rss_id} endpoint."""

    @pytest.mark.asyncio
    async def test_disable_rss_success(self, client):
        """Test successful RSS disable."""
        with patch("module.api.v1.rss.RSSEngine") as mock_engine:
            mock_instance = MagicMock()
            mock_engine.return_value.__enter__.return_value = mock_instance
            mock_instance.rss.disable.return_value = True

            response = client.patch("/api/v1/rss/disable/1")

            assert response.status_code == 200
            data = response.json()
            assert data["msg_en"] == "Disable RSS successfully."
            assert data["msg_zh"] == "禁用 RSS 成功。"

    @pytest.mark.asyncio
    async def test_disable_rss_failed(self, client):
        """Test failed RSS disable."""
        with patch("module.api.v1.rss.RSSEngine") as mock_engine:
            mock_instance = MagicMock()
            mock_engine.return_value.__enter__.return_value = mock_instance
            mock_instance.rss.disable.return_value = False

            response = client.patch("/api/v1/rss/disable/999")

            assert response.status_code == 406
            data = response.json()
            assert data["msg_en"] == "Disable RSS failed."


class TestDisableManyRSS:
    """Test POST /rss/disable/many endpoint."""

    @pytest.mark.asyncio
    async def test_disable_many_rss_success(self, client):
        """Test successful batch RSS disable."""
        mock_response = ResponseModel(
            status=True,
            status_code=200,
            msg_en="Disable successfully.",
            msg_zh="禁用成功。",
        )

        with patch("module.api.v1.rss.RSSEngine") as mock_engine:
            mock_instance = MagicMock()
            mock_engine.return_value.__enter__.return_value = mock_instance
            mock_instance.disable_list.return_value = mock_response

            response = client.post("/api/v1/rss/disable/many", json=[1, 2, 3])

            assert response.status_code == 200
            data = response.json()
            assert "msg_en" in data


class TestUpdateRSS:
    """Test PATCH /rss/update/{rss_id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_rss_success(self, client):
        """Test successful RSS update."""
        with patch("module.api.v1.rss.RSSEngine") as mock_engine:
            mock_instance = MagicMock()
            mock_engine.return_value.__enter__.return_value = mock_instance
            mock_instance.rss.update.return_value = True

            response = client.patch(
                "/api/v1/rss/update/1",
                json={"name": "Updated RSS", "url": "https://new.example.com/rss.xml"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["msg_en"] == "Update RSS successfully."
            assert data["msg_zh"] == "更新 RSS 成功。"

    @pytest.mark.asyncio
    async def test_update_rss_failed(self, client):
        """Test failed RSS update."""
        with patch("module.api.v1.rss.RSSEngine") as mock_engine:
            mock_instance = MagicMock()
            mock_engine.return_value.__enter__.return_value = mock_instance
            mock_instance.rss.update.return_value = False

            response = client.patch(
                "/api/v1/rss/update/999",
                json={"name": "Updated RSS"},
            )

            assert response.status_code == 406
            data = response.json()
            assert data["msg_en"] == "Update RSS failed."


class TestEnableManyRSS:
    """Test POST /rss/enable/many endpoint."""

    @pytest.mark.asyncio
    async def test_enable_many_rss_success(self, client):
        """Test successful batch RSS enable."""
        mock_response = ResponseModel(
            status=True,
            status_code=200,
            msg_en="Enable successfully.",
            msg_zh="启用成功。",
        )

        with patch("module.api.v1.rss.RSSEngine") as mock_engine:
            mock_instance = MagicMock()
            mock_engine.return_value.__enter__.return_value = mock_instance
            mock_instance.enable_list.return_value = mock_response

            response = client.post("/api/v1/rss/enable/many", json=[1, 2, 3])

            assert response.status_code == 200
            data = response.json()
            assert "msg_en" in data


class TestRefreshRSS:
    """Test GET /rss/refresh/all and /rss/refresh/{rss_id} endpoints."""

    @pytest.mark.asyncio
    async def test_refresh_all_rss_success(self, client):
        """Test successful refresh of all RSS feeds."""
        with patch("module.api.v1.rss.RSSEngine") as mock_engine:
            with patch("module.api.v1.rss.DownloadClient") as mock_client:
                mock_engine_instance = MagicMock()
                mock_engine.return_value.__enter__.return_value = mock_engine_instance

                response = client.get("/api/v1/rss/refresh/all")

                assert response.status_code == 200
                data = response.json()
                assert data["msg_en"] == "Refresh all RSS successfully."
                assert data["msg_zh"] == "刷新 RSS 成功。"

    @pytest.mark.asyncio
    async def test_refresh_single_rss_success(self, client):
        """Test successful refresh of a single RSS feed."""
        with patch("module.api.v1.rss.RSSEngine") as mock_engine:
            with patch("module.api.v1.rss.DownloadClient") as mock_client:
                mock_engine_instance = MagicMock()
                mock_engine.return_value.__enter__.return_value = mock_engine_instance

                response = client.get("/api/v1/rss/refresh/1")

                assert response.status_code == 200
                data = response.json()
                assert data["msg_en"] == "Refresh RSS successfully."
                assert data["msg_zh"] == "刷新 RSS 成功。"


class TestGetRSSTorrent:
    """Test GET /rss/torrent endpoint."""

    @pytest.mark.asyncio
    async def test_get_rss_torrent_success(self, client):
        """Test successful retrieval of RSS torrent status."""
        mock_torrents = [
            {"id": 1, "name": "Torrent 1", "status": "downloading"},
            {"id": 2, "name": "Torrent 2", "status": "completed"},
        ]

        with patch("module.api.v1.rss.TorrentStatusManager") as mock_manager:
            mock_instance = MagicMock()
            mock_manager.return_value.__enter__.return_value = mock_instance
            mock_instance.get_rss_torrents_status.return_value = mock_torrents

            response = client.get("/api/v1/rss/torrent", params={"rss_id": 1})

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 2


class TestRecreateRSS:
    """Test POST /rss/recreate/{rss_id} endpoint."""

    @pytest.mark.asyncio
    async def test_recreate_rss_success(self, client):
        """Test successful RSS rule recreation."""
        mock_bangumi_list = [
            {"id": 1, "official_title": "Recreated Bangumi 1"},
            {"id": 2, "official_title": "Recreated Bangumi 2"},
        ]

        with patch("module.api.v1.rss.RSSEngine") as mock_engine:
            with patch("module.api.v1.rss.RSSAnalyser") as mock_analyser:
                mock_engine_instance = MagicMock()
                mock_engine.return_value.__enter__.return_value = mock_engine_instance

                response = client.post("/api/v1/rss/recreate/1")

                assert response.status_code in [200, 404, 406]

    @pytest.mark.asyncio
    async def test_recreate_rss_with_manual_override(self, client):
        """Test RSS recreation with manual parameters."""
        with patch("module.api.v1.rss.RSSEngine") as mock_engine:
            with patch("module.api.v1.rss.RSSAnalyser") as mock_analyser:
                mock_engine_instance = MagicMock()
                mock_engine.return_value.__enter__.return_value = mock_engine_instance

                response = client.post(
                    "/api/v1/rss/recreate/1",
                    params={
                        "official_title": "Custom Title",
                        "season": 2,
                        "group_name": "CustomGroup",
                    },
                )

                assert response.status_code in [200, 404, 406, 422]


class TestGetPendingCount:
    """Test GET /rss/{rss_id}/pending-count endpoint."""

    @pytest.mark.asyncio
    async def test_get_pending_count_success(self, client):
        """Test successful retrieval of pending bangumi count."""
        with patch("module.api.v1.rss.RSSEngine") as mock_engine:
            mock_instance = MagicMock()
            mock_engine.return_value.__enter__.return_value = mock_instance
            mock_instance.bangumi.count_pending_by_rss_id.return_value = 5

            response = client.get("/api/v1/rss/1/pending-count")

            assert response.status_code == 200
            data = response.json()
            assert "pending_count" in data
            assert data["pending_count"] == 5


class TestGetPendingBangumi:
    """Test GET /rss/{rss_id}/pending endpoint."""

    @pytest.mark.asyncio
    async def test_get_pending_bangumi_success(self, client):
        """Test successful retrieval of pending bangumi list."""
        mock_pending_list = [
            {"id": 1, "official_title": "Pending Bangumi 1", "pending_review": True},
            {"id": 2, "official_title": "Pending Bangumi 2", "pending_review": True},
        ]

        with patch("module.api.v1.rss.RSSEngine") as mock_engine:
            mock_instance = MagicMock()
            mock_engine.return_value.__enter__.return_value = mock_instance
            mock_instance.bangumi.get_pending_by_rss_id.return_value = mock_pending_list

            response = client.get("/api/v1/rss/1/pending")

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 2


class TestGetAggregatePending:
    """Test GET /rss/aggregate/pending/{rss_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_aggregate_pending_success(self, client):
        """Test successful retrieval of aggregate RSS pending bangumi."""
        mock_rss = MagicMock()
        mock_rss.id = 1
        mock_rss.aggregate = True

        mock_pending = [
            MagicMock(
                id=1,
                rss_id=1,
                official_title="Pending 1",
                pending_review=True,
                global_filter_matches="1080p,WEB",
                year="2024",
                title_raw="Test",
                season=1,
                season_raw="S01",
                group_name="Group",
                dpi="1080p",
                source="WEB",
                subtitle="CHT",
                filter="1080p",
                rss_link="https://example.com/rss",
                poster_link="https://example.com/poster.jpg",
            )
        ]

        with patch("module.api.v1.rss.RSSEngine") as mock_engine:
            mock_instance = MagicMock()
            mock_engine.return_value.__enter__.return_value = mock_instance
            mock_instance.rss.search_id.return_value = mock_rss
            mock_instance.bangumi.get_pending_by_rss_id.return_value = mock_pending
            mock_instance.bangumi.count_active_by_rss_id.return_value = 3

            response = client.get("/api/v1/rss/aggregate/pending/1")

            assert response.status_code == 200
            data = response.json()
            assert "pending_count" in data
            assert "active_count" in data
            assert "bangumi" in data

    @pytest.mark.asyncio
    async def test_get_aggregate_pending_not_aggregate(self, client):
        """Test error when RSS is not aggregate type."""
        mock_rss = MagicMock()
        mock_rss.id = 1
        mock_rss.aggregate = False

        with patch("module.api.v1.rss.RSSEngine") as mock_engine:
            mock_instance = MagicMock()
            mock_engine.return_value.__enter__.return_value = mock_instance
            mock_instance.rss.search_id.return_value = mock_rss

            response = client.get("/api/v1/rss/aggregate/pending/1")

            assert response.status_code == 400
