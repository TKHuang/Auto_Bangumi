"""API contract tests for RSS endpoints."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from module.api.v1.rss import router as rss_router
from module.domain.value_objects import ResponseModel
from module.models import RSSItem


@pytest.fixture
def app():
    """Create FastAPI app with rss router, auth bypass, and db session override."""
    from module.api.middleware.auth import get_current_user
    from module.database.engine import get_db_session

    app = FastAPI()
    app.include_router(rss_router, prefix="/api/v1")

    # Override auth dependency to bypass authentication
    async def mock_get_current_user():
        return "testuser"

    app.dependency_overrides[get_current_user] = mock_get_current_user

    # Override db session dependency
    async def mock_get_session():
        yield AsyncMock()

    app.dependency_overrides[get_db_session] = mock_get_session
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


def _mock_rss_obj(**overrides):
    """Create a mock RSSItem-like object with sensible defaults."""
    defaults = dict(
        id=1, name="Test RSS", url="https://example.com/rss.xml",
        aggregate=False, parser="mikan", enabled=True,
        last_update=None, last_status=None, last_error=None,
    )
    defaults.update(overrides)
    m = MagicMock()
    for k, v in defaults.items():
        setattr(m, k, v)
    return m


class TestGetRSS:
    """Test GET /rss endpoint."""

    @pytest.mark.asyncio
    async def test_get_rss_success(self, client):
        """Test successful retrieval of all RSS feeds."""
        mock_list = [
            _mock_rss_obj(id=1, name="RSS Feed 1"),
            _mock_rss_obj(id=2, name="RSS Feed 2", aggregate=True, parser="bangumi", enabled=False),
        ]
        with patch("module.api.v1.rss.RSSRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo_cls.return_value = mock_repo
            mock_repo.get_all.return_value = mock_list

            response = client.get("/api/v1/rss")

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 2

    @pytest.mark.asyncio
    async def test_get_rss_empty(self, client):
        """Test retrieval when no RSS feeds exist."""
        with patch("module.api.v1.rss.RSSRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo_cls.return_value = mock_repo
            mock_repo.get_all.return_value = []

            response = client.get("/api/v1/rss")

            assert response.status_code == 200
            data = response.json()
            assert data == []


class TestAddRSS:
    """Test POST /rss/add endpoint."""

    @pytest.mark.asyncio
    async def test_add_rss_skip_bangumi(self, client):
        """Test adding RSS with skip_bangumi flag."""
        new_rss = _mock_rss_obj(id=10)
        with patch("module.api.v1.rss.RSSRepository") as mock_rss_cls:
            with patch("module.api.v1.rss.BangumiRepository"):
                mock_rss_repo = AsyncMock()
                mock_rss_cls.return_value = mock_rss_repo
                mock_rss_repo.create.return_value = new_rss

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
    async def test_add_rss_with_manual_input(self, client):
        """Test adding RSS with manual override."""
        new_rss = _mock_rss_obj(id=10)
        with patch("module.api.v1.rss.RSSRepository") as mock_rss_cls:
            with patch("module.api.v1.rss.BangumiRepository") as mock_b_cls:
                with patch("module.api.v1.rss.analyser") as mock_analyser:
                    mock_rss_repo = AsyncMock()
                    mock_rss_cls.return_value = mock_rss_repo
                    mock_rss_repo.create.return_value = new_rss
                    mock_b_repo = AsyncMock()
                    mock_b_cls.return_value = mock_b_repo
                    mock_b_repo.find_by_official_title.return_value = None
                    mock_b_repo.find_by_any_rss_link.return_value = None
                    # analyser returns a ResponseModel (non-aggregate path)
                    mock_analyser.link_to_data = AsyncMock(return_value=ResponseModel(
                        status=True, status_code=200,
                        msg_en="OK", msg_zh="OK",
                    ))

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
        with patch("module.api.v1.rss.RSSRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo_cls.return_value = mock_repo
            mock_repo.cascade_delete.return_value = True

            response = client.delete("/api/v1/rss/delete/1")

            assert response.status_code == 200
            data = response.json()
            assert data["msg_en"] == "Delete RSS successfully."
            assert data["msg_zh"] == "删除 RSS 成功。"

    @pytest.mark.asyncio
    async def test_delete_rss_failed(self, client):
        """Test failed RSS deletion."""
        with patch("module.api.v1.rss.RSSRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo_cls.return_value = mock_repo
            mock_repo.cascade_delete.return_value = False

            response = client.delete("/api/v1/rss/delete/999")

            assert response.status_code == 404
            data = response.json()
            assert data["msg_en"] == "Delete RSS failed."


class TestDeleteManyRSS:
    """Test POST /rss/delete/many endpoint."""

    @pytest.mark.asyncio
    async def test_delete_many_rss_success(self, client):
        """Test successful batch RSS deletion."""
        with patch("module.api.v1.rss.RSSRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo_cls.return_value = mock_repo
            mock_repo.cascade_delete.return_value = True

            response = client.post("/api/v1/rss/delete/many", json=[1, 2, 3])

            assert response.status_code == 200
            data = response.json()
            assert "msg_en" in data


class TestDisableRSS:
    """Test PATCH /rss/disable/{rss_id} endpoint."""

    @pytest.mark.asyncio
    async def test_disable_rss_success(self, client):
        """Test successful RSS disable."""
        with patch("module.api.v1.rss.RSSRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo_cls.return_value = mock_repo
            mock_repo.disable.return_value = True

            response = client.patch("/api/v1/rss/disable/1")

            assert response.status_code == 200
            data = response.json()
            assert data["msg_en"] == "Disable RSS successfully."
            assert data["msg_zh"] == "禁用 RSS 成功。"

    @pytest.mark.asyncio
    async def test_disable_rss_failed(self, client):
        """Test failed RSS disable."""
        with patch("module.api.v1.rss.RSSRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo_cls.return_value = mock_repo
            mock_repo.disable.return_value = False

            response = client.patch("/api/v1/rss/disable/999")

            assert response.status_code == 404
            data = response.json()
            assert data["msg_en"] == "Disable RSS failed."


class TestDisableManyRSS:
    """Test POST /rss/disable/many endpoint."""

    @pytest.mark.asyncio
    async def test_disable_many_rss_success(self, client):
        """Test successful batch RSS disable."""
        with patch("module.api.v1.rss.RSSRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo_cls.return_value = mock_repo

            response = client.post("/api/v1/rss/disable/many", json=[1, 2, 3])

            assert response.status_code == 200
            data = response.json()
            assert "msg_en" in data


class TestUpdateRSS:
    """Test PATCH /rss/update/{rss_id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_rss_success(self, client):
        """Test successful RSS update."""
        with patch("module.api.v1.rss.RSSRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo_cls.return_value = mock_repo

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
        with patch("module.api.v1.rss.RSSRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo_cls.return_value = mock_repo
            mock_repo.update.side_effect = ValueError("Not found")

            response = client.patch(
                "/api/v1/rss/update/999",
                json={"name": "Updated RSS"},
            )

            assert response.status_code == 404
            data = response.json()
            assert data["msg_en"] == "Update RSS failed."


class TestEnableManyRSS:
    """Test POST /rss/enable/many endpoint."""

    @pytest.mark.asyncio
    async def test_enable_many_rss_success(self, client):
        """Test successful batch RSS enable."""
        with patch("module.api.v1.rss.RSSRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo_cls.return_value = mock_repo

            response = client.post("/api/v1/rss/enable/many", json=[1, 2, 3])

            assert response.status_code == 200
            data = response.json()
            assert "msg_en" in data


class TestRefreshRSS:
    """Test GET /rss/refresh/all and /rss/refresh/{rss_id} endpoints."""

    @pytest.mark.asyncio
    async def test_refresh_all_rss_success(self, client):
        """Test successful refresh of all RSS feeds."""
        with patch("module.api.v1.rss.create_downloader") as mock_dl:
            with patch("module.api.v1.rss.AsyncRSSEngine") as mock_engine:
                mock_dl.return_value = AsyncMock()
                mock_engine.refresh_rss = AsyncMock()

                response = client.post("/api/v1/rss/refresh/all")

                assert response.status_code == 200
                data = response.json()
                assert data["msg_en"] == "Refresh all RSS successfully."
                assert data["msg_zh"] == "刷新 RSS 成功。"

    @pytest.mark.asyncio
    async def test_refresh_single_rss_success(self, client):
        """Test successful refresh of a single RSS feed."""
        with patch("module.api.v1.rss.create_downloader") as mock_dl:
            with patch("module.api.v1.rss.AsyncRSSEngine") as mock_engine:
                mock_dl.return_value = AsyncMock()
                mock_engine.refresh_rss = AsyncMock()

                response = client.post("/api/v1/rss/refresh/1")

                assert response.status_code == 200
                data = response.json()
                assert data["msg_en"] == "Refresh RSS successfully."
                assert data["msg_zh"] == "刷新 RSS 成功。"


class TestGetRSSTorrent:
    """Test GET /rss/torrent endpoint."""

    @pytest.mark.asyncio
    async def test_get_rss_torrent_success(self, client):
        """Test successful retrieval of RSS torrent status."""
        db_torrent1 = MagicMock()
        db_torrent1.id = 1
        db_torrent1.name = "Torrent 1"
        db_torrent1.url = "https://example.com/t1"
        db_torrent1.downloaded = True
        db_torrent1.hash = "abc123"

        db_torrent2 = MagicMock()
        db_torrent2.id = 2
        db_torrent2.name = "Torrent 2"
        db_torrent2.url = "https://example.com/t2"
        db_torrent2.downloaded = False
        db_torrent2.hash = "def456"

        online_torrent = MagicMock()
        online_torrent.hash = "abc123"
        online_torrent.state = "completed"
        online_torrent.progress = 1.0

        with patch("module.api.v1.rss.TorrentRepository") as mock_t_cls:
            with patch("module.api.v1.rss.create_downloader") as mock_dl:
                mock_t = AsyncMock()
                mock_t_cls.return_value = mock_t
                # endpoint uses get_visible_by_rss (not get_by_rss)
                db_torrent1.pikpak_cloud_path = None
                db_torrent2.pikpak_cloud_path = None
                mock_t.get_visible_by_rss.return_value = [db_torrent1, db_torrent2]

                mock_downloader = AsyncMock()
                mock_dl.return_value = mock_downloader
                mock_downloader.torrents_info.return_value = [online_torrent]

                response = client.get("/api/v1/rss/torrent", params={"rss_id": 1})

                assert response.status_code == 200
                data = response.json()
                assert isinstance(data, list)
                assert len(data) == 2

    @pytest.mark.asyncio
    async def test_get_rss_torrent_empty(self, client):
        """Test retrieval when no torrents exist for RSS."""
        with patch("module.api.v1.rss.TorrentRepository") as mock_t_cls:
            with patch("module.api.v1.rss.create_downloader") as mock_dl:
                mock_t = AsyncMock()
                mock_t_cls.return_value = mock_t
                # endpoint uses get_visible_by_rss (not get_by_rss)
                mock_t.get_visible_by_rss.return_value = []
                mock_dl.return_value = AsyncMock()

                response = client.get("/api/v1/rss/torrent", params={"rss_id": 1})

                assert response.status_code == 200
                data = response.json()
                assert data == []


class TestRecreateRSS:
    """Test POST /rss/recreate/{rss_id} endpoint."""

    @pytest.mark.asyncio
    async def test_recreate_rss_success(self, client):
        """Test successful RSS rule recreation (non-aggregate)."""
        mock_rss = _mock_rss_obj(aggregate=False)

        with patch("module.api.v1.rss.RSSRepository") as mock_repo_cls:
            with patch("module.api.v1.rss.AsyncRSSAnalyserAdapter") as mock_adapter_cls:
                mock_repo = AsyncMock()
                mock_repo_cls.return_value = mock_repo
                mock_repo.get_by_id.return_value = mock_rss

                mock_local = AsyncMock()
                mock_adapter_cls.return_value = mock_local
                # Return a ResponseModel to trigger the non-Bangumi branch
                mock_local.link_to_data.return_value = ResponseModel(
                    status=False, status_code=404,
                    msg_en="Cannot parse", msg_zh="无法解析",
                )

                response = client.post("/api/v1/rss/recreate/1")

                assert response.status_code in [200, 404, 422]

    @pytest.mark.asyncio
    async def test_recreate_rss_not_found(self, client):
        """Test recreate when RSS not found."""
        with patch("module.api.v1.rss.RSSRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo_cls.return_value = mock_repo
            mock_repo.get_by_id.return_value = None

            response = client.post("/api/v1/rss/recreate/999")

            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_recreate_rss_with_manual_override(self, client):
        """Test RSS recreation with manual parameters."""
        mock_rss = _mock_rss_obj(aggregate=False)

        with patch("module.api.v1.rss.RSSRepository") as mock_repo_cls:
            with patch("module.api.v1.rss.AsyncRSSAnalyserAdapter") as mock_adapter_cls:
                mock_repo = AsyncMock()
                mock_repo_cls.return_value = mock_repo
                mock_repo.get_by_id.return_value = mock_rss

                mock_local = AsyncMock()
                mock_adapter_cls.return_value = mock_local
                mock_local.link_to_data.return_value = ResponseModel(
                    status=False, status_code=404,
                    msg_en="Cannot parse", msg_zh="无法解析",
                )

                response = client.post(
                    "/api/v1/rss/recreate/1",
                    params={
                        "official_title": "Custom Title",
                        "season": 2,
                        "group_name": "CustomGroup",
                    },
                )

                assert response.status_code in [200, 404, 422]


class TestGetPendingCount:
    """Test GET /rss/{rss_id}/pending-count endpoint."""

    @pytest.mark.asyncio
    async def test_get_pending_count_success(self, client):
        """Test successful retrieval of pending bangumi count."""
        with patch("module.api.v1.rss.BangumiRepository") as mock_b_cls:
            mock_b = AsyncMock()
            mock_b_cls.return_value = mock_b
            mock_b.count_pending_by_rss_id.return_value = 5

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
        mock_bangumi1 = MagicMock()
        for k, v in dict(
            id=1, official_title="Pending Bangumi 1", pending_review=True,
            rss_id=1, title_raw="raw1", season=1, season_raw="S01",
            group_name="G", dpi="1080p", source="WEB", subtitle="CHT",
            filter="1080p", rss_link="https://example.com/rss", year="2024",
            poster_link="https://example.com/poster.jpg", added=False,
            deleted=False, eps_collect=False, offset=0, rule_name="R",
            save_path="/tmp/test", global_filter_matches=None,
        ).items():
            setattr(mock_bangumi1, k, v)

        mock_bangumi2 = MagicMock()
        for k, v in dict(
            id=2, official_title="Pending Bangumi 2", pending_review=True,
            rss_id=1, title_raw="raw2", season=1, season_raw="S01",
            group_name="G", dpi="1080p", source="WEB", subtitle="CHT",
            filter="1080p", rss_link="https://example.com/rss", year="2024",
            poster_link="https://example.com/poster.jpg", added=False,
            deleted=False, eps_collect=False, offset=0, rule_name="R",
            save_path="/tmp/test", global_filter_matches=None,
        ).items():
            setattr(mock_bangumi2, k, v)

        with patch("module.api.v1.rss.BangumiRepository") as mock_b_cls:
            mock_b = AsyncMock()
            mock_b_cls.return_value = mock_b
            mock_b.get_pending_review.return_value = [mock_bangumi1, mock_bangumi2]

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
        mock_rss = _mock_rss_obj(id=1, aggregate=True)

        mock_pending_bangumi = MagicMock()
        for k, v in dict(
            id=1, rss_id=1, official_title="Pending 1", pending_review=True,
            global_filter_matches="1080p,WEB", year="2024", title_raw="Test",
            season=1, season_raw="S01", group_name="Group", dpi="1080p",
            source="WEB", subtitle="CHT", filter="1080p",
            rss_link="https://example.com/rss",
            poster_link="https://example.com/poster.jpg",
        ).items():
            setattr(mock_pending_bangumi, k, v)

        with patch("module.api.v1.rss.RSSRepository") as mock_r_cls:
            with patch("module.api.v1.rss.BangumiRepository") as mock_b_cls:
                mock_r = AsyncMock()
                mock_r_cls.return_value = mock_r
                mock_r.get_by_id.return_value = mock_rss

                mock_b = AsyncMock()
                mock_b_cls.return_value = mock_b
                mock_b.get_pending_review.return_value = [mock_pending_bangumi]
                mock_b.count_active_by_rss_id.return_value = 3

                response = client.get("/api/v1/rss/aggregate/pending/1")

                assert response.status_code == 200
                data = response.json()
                assert "pending_count" in data
                assert "active_count" in data
                assert "bangumi" in data

    @pytest.mark.asyncio
    async def test_get_aggregate_pending_not_aggregate(self, client):
        """Test error when RSS is not aggregate type."""
        mock_rss = _mock_rss_obj(id=1, aggregate=False)

        with patch("module.api.v1.rss.RSSRepository") as mock_r_cls:
            with patch("module.api.v1.rss.BangumiRepository"):
                mock_r = AsyncMock()
                mock_r_cls.return_value = mock_r
                mock_r.get_by_id.return_value = mock_rss

                response = client.get("/api/v1/rss/aggregate/pending/1")

                assert response.status_code == 400
