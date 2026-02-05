"""API contract tests for bangumi endpoints."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from module.api.v1.bangumi import router as bangumi_router
from module.models.bangumi import Bangumi, BangumiUpdate
from module.models.response import ResponseModel


@pytest.fixture
def app():
    """Create FastAPI app with bangumi router and auth bypass."""
    from module.api.middleware.auth import get_current_user
    
    app = FastAPI()
    app.include_router(bangumi_router, prefix="/api/v1")
    
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
def mock_bangumi():
    """Create mock bangumi object."""
    return Bangumi(
        id=1,
        official_title="Test Bangumi",
        title_raw="[Group] Test Bangumi - 01 [1080p]",
        season=1,
        season_raw="S01",
        group_name="Group",
        dpi="1080p",
        source="WEB-DL",
        subtitle="CHT",
        filter="1080p,WEB-DL",
        rss_link="https://example.com/rss",
        poster_link="https://example.com/poster.jpg",
        year="2024",
        added=True,
        deleted=False,
        eps_collect=False,
        offset=0,
        rule_name="Test Bangumi",
        save_path="/downloads/Bangumi/Test Bangumi",
        rss_id=1,
    )


class TestGetAllBangumi:
    """Test GET /bangumi/get/all endpoint."""

    @pytest.mark.asyncio
    async def test_get_all_success(self, client):
        """Test successful retrieval of all bangumi."""
        mock_bangumi_list = [
            {
                "id": 1,
                "official_title": "Test Bangumi 1",
                "title_raw": "[Group] Test 1",
                "season": 1,
                "filter": "1080p,WEB",
                "rss_link": "https://example.com/rss1",
            },
            {
                "id": 2,
                "official_title": "Test Bangumi 2",
                "title_raw": "[Group] Test 2",
                "season": 2,
                "filter": "720p",
                "rss_link": "https://example.com/rss2",
            },
        ]

        with patch("module.api.v1.bangumi.TorrentManager") as mock_manager:
            mock_instance = MagicMock()
            mock_manager.return_value.__enter__.return_value = mock_instance
            mock_instance.bangumi.search_all.return_value = mock_bangumi_list

            response = client.get("/api/v1/bangumi/get/all")

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 2
            assert data[0]["official_title"] == "Test Bangumi 1"
            # Verify filter is a STRING (comma-separated), not array
            assert isinstance(data[0]["filter"], str)
            assert isinstance(data[0]["rss_link"], str)

    @pytest.mark.asyncio
    async def test_get_all_empty(self, client):
        """Test retrieval when no bangumi exist."""
        with patch("module.api.v1.bangumi.TorrentManager") as mock_manager:
            mock_instance = MagicMock()
            mock_manager.return_value.__enter__.return_value = mock_instance
            mock_instance.bangumi.search_all.return_value = []

            response = client.get("/api/v1/bangumi/get/all")

            assert response.status_code == 200
            data = response.json()
            assert data == []


class TestGetBangumiById:
    """Test GET /bangumi/get/{bangumi_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_by_id_success(self, client, mock_bangumi):
        """Test successful retrieval of a specific bangumi."""
        with patch("module.api.v1.bangumi.TorrentManager") as mock_manager:
            mock_instance = MagicMock()
            mock_manager.return_value.__enter__.return_value = mock_instance
            mock_instance.search_one.return_value = mock_bangumi

            response = client.get("/api/v1/bangumi/get/1")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == 1
            assert data["official_title"] == "Test Bangumi"
            # Verify filter and rss_link are STRINGS
            assert isinstance(data["filter"], str)
            assert isinstance(data["rss_link"], str)

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, client):
        """Test retrieval of non-existent bangumi."""
        with patch("module.api.v1.bangumi.TorrentManager") as mock_manager:
            mock_instance = MagicMock()
            mock_manager.return_value.__enter__.return_value = mock_instance
            # Return empty dict to avoid validation error
            mock_instance.search_one.return_value = {}

            response = client.get("/api/v1/bangumi/get/999")

            assert response.status_code == 200


class TestUpdateBangumi:
    """Test PATCH /bangumi/update/{bangumi_id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_success(self, client):
        """Test successful bangumi update."""
        update_data = {
            "official_title": "Updated Bangumi",
            "title_raw": "[Group] Updated - 01",
            "season": 2,
            "season_raw": "S02",
            "group_name": "Group",
            "dpi": "1080p",
            "source": "WEB-DL",
            "subtitle": "CHT",
            "filter": "1080p",
            "rss_link": "https://example.com/new",
            "poster_link": "",
            "year": "2024",
            "added": False,
            "deleted": False,
            "eps_collect": False,
            "offset": 0,
            "rule_name": "Updated Bangumi",
            "save_path": "/downloads",
            "rss_id": 1,
        }

        mock_response = ResponseModel(
            status=True,
            status_code=200,
            msg_en="Update successfully.",
            msg_zh="更新成功。",
        )

        with patch("module.api.v1.bangumi.TorrentManager") as mock_manager:
            mock_instance = MagicMock()
            mock_manager.return_value.__enter__.return_value = mock_instance
            mock_instance.update_rule.return_value = mock_response

            response = client.patch("/api/v1/bangumi/update/1", json=update_data)

            assert response.status_code == 200
            data = response.json()
            assert "msg_en" in data
            assert "msg_zh" in data
            assert data["msg_en"] == "Update successfully."

    @pytest.mark.asyncio
    async def test_update_not_found(self, client):
        """Test update of non-existent bangumi."""
        update_data = {
            "official_title": "Updated Bangumi",
            "title_raw": "[Group] Updated - 01",
            "season": 2,
            "season_raw": "S02",
            "group_name": "Group",
            "dpi": "1080p",
            "source": "WEB-DL",
            "subtitle": "CHT",
            "filter": "1080p",
            "rss_link": "https://example.com/new",
            "poster_link": "",
            "year": "2024",
            "added": False,
            "deleted": False,
            "eps_collect": False,
            "offset": 0,
            "rule_name": "Updated Bangumi",
            "save_path": "/downloads",
            "rss_id": 1,
        }

        mock_response = ResponseModel(
            status=False,
            status_code=404,
            msg_en="Bangumi not found.",
            msg_zh="番剧未找到。",
        )

        with patch("module.api.v1.bangumi.TorrentManager") as mock_manager:
            mock_instance = MagicMock()
            mock_manager.return_value.__enter__.return_value = mock_instance
            mock_instance.update_rule.return_value = mock_response

            response = client.patch("/api/v1/bangumi/update/999", json=update_data)

            assert response.status_code == 404


class TestDeleteBangumi:
    """Test DELETE /bangumi/delete/{bangumi_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_success(self, client):
        """Test successful bangumi deletion."""
        mock_response = ResponseModel(
            status=True,
            status_code=200,
            msg_en="Delete successfully.",
            msg_zh="删除成功。",
        )

        with patch("module.api.v1.bangumi.TorrentManager") as mock_manager:
            mock_instance = MagicMock()
            mock_manager.return_value.__enter__.return_value = mock_instance
            mock_instance.delete_rule.return_value = mock_response

            response = client.delete("/api/v1/bangumi/delete/1", params={"file": False})

            assert response.status_code == 200
            data = response.json()
            assert "msg_en" in data
            assert "msg_zh" in data

    @pytest.mark.asyncio
    async def test_delete_with_files(self, client):
        """Test bangumi deletion with associated files."""
        mock_response = ResponseModel(
            status=True,
            status_code=200,
            msg_en="Delete successfully.",
            msg_zh="删除成功。",
        )

        with patch("module.api.v1.bangumi.TorrentManager") as mock_manager:
            mock_instance = MagicMock()
            mock_manager.return_value.__enter__.return_value = mock_instance
            mock_instance.delete_rule.return_value = mock_response

            response = client.delete("/api/v1/bangumi/delete/1", params={"file": True})

            assert response.status_code == 200
            # Verify file parameter was passed
            mock_instance.delete_rule.assert_called_with(1, True)


class TestDeleteManyBangumi:
    """Test DELETE /bangumi/delete (batch) endpoint."""

    @pytest.mark.asyncio
    async def test_delete_many_success(self, client):
        """Test successful batch deletion."""
        mock_response = ResponseModel(
            status=True,
            status_code=200,
            msg_en="Delete successfully.",
            msg_zh="删除成功。",
        )

        with patch("module.api.v1.bangumi.TorrentManager") as mock_manager:
            mock_instance = MagicMock()
            mock_manager.return_value.__enter__.return_value = mock_instance
            mock_instance.delete_many_rules.return_value = mock_response

            response = client.request(
                "DELETE",
                "/api/v1/bangumi/delete",
                json=[1, 2, 3],
                params={"file": False},
            )

            assert response.status_code == 200
            data = response.json()
            assert "msg_en" in data
            assert "msg_zh" in data


class TestDisableBangumi:
    """Test DELETE /bangumi/disable/{bangumi_id} endpoint."""

    @pytest.mark.asyncio
    async def test_disable_success(self, client):
        """Test successful bangumi disable."""
        mock_response = ResponseModel(
            status=True,
            status_code=200,
            msg_en="Disable successfully.",
            msg_zh="禁用成功。",
        )

        with patch("module.api.v1.bangumi.TorrentManager") as mock_manager:
            mock_instance = MagicMock()
            mock_manager.return_value.__enter__.return_value = mock_instance
            mock_instance.disable_rule.return_value = mock_response

            response = client.delete("/api/v1/bangumi/disable/1", params={"file": False})

            assert response.status_code == 200
            data = response.json()
            assert "msg_en" in data
            assert "msg_zh" in data


class TestDisableManyBangumi:
    """Test DELETE /bangumi/disable (batch) endpoint."""

    @pytest.mark.asyncio
    async def test_disable_many_success(self, client):
        """Test successful batch disable."""
        mock_response = ResponseModel(
            status=True,
            status_code=200,
            msg_en="Disable successfully.",
            msg_zh="禁用成功。",
        )

        with patch("module.api.v1.bangumi.TorrentManager") as mock_manager:
            mock_instance = MagicMock()
            mock_manager.return_value.__enter__.return_value = mock_instance
            mock_instance.disable_many_rules.return_value = mock_response

            response = client.request(
                "DELETE",
                "/api/v1/bangumi/disable",
                json=[1, 2, 3],
                params={"file": False},
            )

            assert response.status_code == 200
            data = response.json()
            assert "msg_en" in data
            assert "msg_zh" in data


class TestEnableBangumi:
    """Test GET /bangumi/enable/{bangumi_id} endpoint."""

    @pytest.mark.asyncio
    async def test_enable_success(self, client):
        """Test successful bangumi enable."""
        mock_response = ResponseModel(
            status=True,
            status_code=200,
            msg_en="Enable successfully.",
            msg_zh="启用成功。",
        )

        with patch("module.api.v1.bangumi.TorrentManager") as mock_manager:
            mock_instance = MagicMock()
            mock_manager.return_value.__enter__.return_value = mock_instance
            mock_instance.enable_rule.return_value = mock_response

            response = client.get("/api/v1/bangumi/enable/1")

            assert response.status_code == 200
            data = response.json()
            assert "msg_en" in data
            assert "msg_zh" in data


class TestResetAllBangumi:
    """Test GET /bangumi/reset/all endpoint."""

    @pytest.mark.asyncio
    async def test_reset_all_success(self, client):
        """Test successful reset of all bangumi."""
        with patch("module.api.v1.bangumi.TorrentManager") as mock_manager:
            mock_instance = MagicMock()
            mock_manager.return_value.__enter__.return_value = mock_instance

            response = client.get("/api/v1/bangumi/reset/all")

            assert response.status_code == 200
            data = response.json()
            assert data["msg_en"] == "Reset all rules successfully."
            assert data["msg_zh"] == "重置所有规则成功。"
            # Verify delete_all and commit were called
            mock_instance.bangumi.delete_all.assert_called_once()
            mock_instance.commit.assert_called_once()


class TestRefreshPoster:
    """Test GET /bangumi/refresh/poster/all endpoint."""

    @pytest.mark.asyncio
    async def test_refresh_poster_all_success(self, client):
        """Test successful refresh of all posters."""
        mock_response = ResponseModel(
            status=True,
            status_code=200,
            msg_en="Refresh poster successfully.",
            msg_zh="刷新海报成功。",
        )

        with patch("module.api.v1.bangumi.TorrentManager") as mock_manager:
            mock_instance = MagicMock()
            mock_manager.return_value.__enter__.return_value = mock_instance
            mock_instance.refresh_poster.return_value = mock_response

            response = client.get("/api/v1/bangumi/refresh/poster/all")

            assert response.status_code == 200
            data = response.json()
            assert "msg_en" in data
            assert "msg_zh" in data


class TestRefreshPosterById:
    """Test GET /bangumi/refresh/poster/{bangumi_id} endpoint."""

    @pytest.mark.asyncio
    async def test_refresh_poster_by_id_success(self, client):
        """Test successful refresh of a specific poster."""
        mock_response = ResponseModel(
            status=True,
            status_code=200,
            msg_en="Refresh poster successfully.",
            msg_zh="刷新海报成功。",
        )

        with patch("module.api.v1.bangumi.TorrentManager") as mock_manager:
            mock_instance = MagicMock()
            mock_manager.return_value.__enter__.return_value = mock_instance
            mock_instance.refind_poster.return_value = mock_response

            response = client.get("/api/v1/bangumi/refresh/poster/1")

            assert response.status_code == 200
            data = response.json()
            assert "msg_en" in data
            assert "msg_zh" in data


class TestGetTorrentStatus:
    """Test GET /bangumi/torrent/{bangumi_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_torrent_status_success(self, client):
        """Test successful retrieval of torrent status."""
        mock_torrents = [
            {"id": 1, "name": "Test Episode 01", "status": "downloading", "progress": 50},
            {"id": 2, "name": "Test Episode 02", "status": "completed", "progress": 100},
        ]

        with patch("module.api.v1.bangumi.TorrentStatusManager") as mock_manager:
            mock_instance = MagicMock()
            mock_manager.return_value.__enter__.return_value = mock_instance
            mock_instance.get_bangumi_torrents_status.return_value = mock_torrents

            response = client.get("/api/v1/bangumi/torrent/1")

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 2
            assert data[0]["name"] == "Test Episode 01"


class TestDownloadTorrent:
    """Test POST /bangumi/torrent/download endpoint."""

    @pytest.mark.asyncio
    async def test_download_torrent_success(self, client):
        """Test successful torrent download."""
        mock_response = ResponseModel(
            status=True,
            status_code=200,
            msg_en="Download torrent successfully.",
            msg_zh="下载种子成功。",
        )

        with patch("module.api.v1.bangumi.TorrentStatusManager") as mock_manager:
            mock_instance = MagicMock()
            mock_manager.return_value.__enter__.return_value = mock_instance
            mock_instance.download_torrent.return_value = mock_response

            response = client.post(
                "/api/v1/bangumi/torrent/download",
                params={"torrent_id": 123},
            )

            assert response.status_code == 200
            data = response.json()
            assert "msg_en" in data
            assert "msg_zh" in data
            # Verify download_torrent was called with correct ID
            mock_instance.download_torrent.assert_called_with(123)


class TestActivatePendingBangumi:
    """Test POST /bangumi/{bangumi_id}/activate endpoint."""

    @pytest.mark.asyncio
    async def test_activate_success(self, client, mock_bangumi):
        """Test successful activation of pending bangumi."""
        mock_download_result = ResponseModel(
            status=True,
            status_code=200,
            msg_en="Downloaded 3 torrents",
            msg_zh="下载了 3 个种子",
        )

        with patch("module.api.v1.bangumi.TorrentManager") as mock_torrent_manager:
            with patch("module.api.v1.bangumi.RSSEngine") as mock_rss_engine:
                mock_torrent_instance = MagicMock()
                mock_torrent_manager.return_value.__enter__.return_value = mock_torrent_instance
                mock_torrent_instance.bangumi.activate_pending.return_value = (True, "Activated")
                mock_torrent_instance.bangumi.search_id.return_value = mock_bangumi

                mock_rss_instance = MagicMock()
                mock_rss_engine.return_value.__enter__.return_value = mock_rss_instance
                mock_rss_instance.download_bangumi.return_value = mock_download_result

                response = client.post("/api/v1/bangumi/1/activate", json={"filter": "1080p"})

                assert response.status_code == 200
                data = response.json()
                assert "msg_en" in data
                assert "msg_zh" in data
                assert "activated" in data["msg_en"].lower()

    @pytest.mark.asyncio
    async def test_activate_not_pending(self, client):
        """Test activation of bangumi not in pending status."""
        with patch("module.api.v1.bangumi.TorrentManager") as mock_manager:
            mock_instance = MagicMock()
            mock_manager.return_value.__enter__.return_value = mock_instance
            mock_instance.bangumi.activate_pending.return_value = (
                False,
                "Bangumi not in pending review status",
            )

            response = client.post("/api/v1/bangumi/1/activate")

            assert response.status_code == 400
            data = response.json()
            assert "msg_en" in data
            assert "msg_zh" in data


class TestRetriggerRename:
    """Test POST /bangumi/{bangumi_id}/retrigger-rename endpoint."""

    @pytest.mark.asyncio
    async def test_retrigger_rename_success(self, client):
        """Test successful re-rename trigger."""
        mock_renamed_files = ["file1.mp4", "file2.mp4", "file3.mp4"]

        with patch("module.api.v1.bangumi.Renamer") as mock_renamer:
            mock_instance = MagicMock()
            mock_renamer.return_value.__enter__.return_value = mock_instance
            mock_instance.rename_bangumi.return_value = mock_renamed_files

            response = client.post("/api/v1/bangumi/1/retrigger-rename")

            assert response.status_code == 200
            data = response.json()
            assert "msg_en" in data
            assert "msg_zh" in data
            assert "3 files" in data["msg_en"] or "3 个文件" in data["msg_zh"]
            # Verify rename_bangumi was called with clear_status=True
            mock_instance.rename_bangumi.assert_called_with(1, clear_status=True)

    @pytest.mark.asyncio
    async def test_retrigger_rename_no_files(self, client):
        """Test re-rename trigger when no files to rename."""
        with patch("module.api.v1.bangumi.Renamer") as mock_renamer:
            mock_instance = MagicMock()
            mock_renamer.return_value.__enter__.return_value = mock_instance
            mock_instance.rename_bangumi.return_value = []

            response = client.post("/api/v1/bangumi/1/retrigger-rename")

            assert response.status_code == 200
            data = response.json()
            assert "0 files" in data["msg_en"] or "0 个文件" in data["msg_zh"]
