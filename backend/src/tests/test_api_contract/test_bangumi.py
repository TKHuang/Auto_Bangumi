"""API contract tests for bangumi endpoints."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from module.api.v1.bangumi import router as bangumi_router
from module.domain.value_objects import ResponseModel
from module.models.bangumi import Bangumi, BangumiUpdate


@pytest.fixture
def app():
    from module.api.middleware.auth import get_current_user
    from module.database.engine import get_db_session

    app = FastAPI()
    app.include_router(bangumi_router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: "testuser"

    async def mock_get_session():
        yield AsyncMock()

    app.dependency_overrides[get_db_session] = mock_get_session
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


def _mock_bangumi_obj(**overrides):
    defaults = dict(
        id=1, official_title="Test Bangumi",
        title_raw="[Group] Test Bangumi - 01 [1080p]",
        season=1, season_raw="S01", group_name="Group",
        dpi="1080p", source="WEB-DL", subtitle="CHT",
        filter="1080p,WEB-DL", rss_link="https://example.com/rss",
        poster_link="https://example.com/poster.jpg", year="2024",
        added=True, deleted=False, eps_collect=False, offset=0,
        rule_name="Test Bangumi", save_path="/downloads/Bangumi/Test Bangumi",
        rss_id=1, pending_review=False, global_filter_matches=None,
    )
    defaults.update(overrides)
    m = MagicMock()
    for k, v in defaults.items():
        setattr(m, k, v)
    return m


class TestGetAllBangumi:

    @pytest.mark.asyncio
    async def test_get_all_success(self, client):
        mock_list = [
            _mock_bangumi_obj(id=1, official_title="Test Bangumi 1"),
            _mock_bangumi_obj(id=2, official_title="Test Bangumi 2", season=2),
        ]
        with patch("module.api.v1.bangumi.BangumiRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo_cls.return_value = mock_repo
            mock_repo.get_all.return_value = mock_list
            response = client.get("/api/v1/bangumi/get/all")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 2

    @pytest.mark.asyncio
    async def test_get_all_empty(self, client):
        with patch("module.api.v1.bangumi.BangumiRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo_cls.return_value = mock_repo
            mock_repo.get_all.return_value = []
            response = client.get("/api/v1/bangumi/get/all")
            assert response.status_code == 200
            assert response.json() == []


class TestGetBangumiById:

    @pytest.mark.asyncio
    async def test_get_by_id_success(self, client):
        with patch("module.api.v1.bangumi.BangumiRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo_cls.return_value = mock_repo
            mock_repo.get_by_id.return_value = _mock_bangumi_obj()
            response = client.get("/api/v1/bangumi/get/1")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, client):
        with patch("module.api.v1.bangumi.BangumiRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo_cls.return_value = mock_repo
            mock_repo.get_by_id.return_value = None
            response = client.get("/api/v1/bangumi/get/999")
            assert response.status_code == 404


class TestUpdateBangumi:

    @pytest.mark.asyncio
    async def test_update_success(self, client):
        update_data = {
            "official_title": "Updated Bangumi", "title_raw": "[Group] Updated - 01",
            "season": 2, "season_raw": "S02", "group_name": "Group",
            "dpi": "1080p", "source": "WEB-DL", "subtitle": "CHT",
            "filter": "1080p", "rss_link": "https://example.com/new",
            "poster_link": "", "year": "2024", "added": False, "deleted": False,
            "eps_collect": False, "offset": 0, "rule_name": "Updated Bangumi",
            "save_path": "/downloads", "rss_id": 1,
        }
        with patch("module.api.v1.bangumi.BangumiRepository") as mock_b_cls:
            with patch("module.api.v1.bangumi.TorrentRepository") as mock_t_cls:
                with patch("module.api.v1.bangumi.create_downloader") as mock_dl:
                    mock_b = AsyncMock()
                    mock_b_cls.return_value = mock_b
                    mock_b.get_by_id.return_value = _mock_bangumi_obj()
                    mock_t = AsyncMock()
                    mock_t_cls.return_value = mock_t
                    mock_dl.return_value = AsyncMock()
                    mock_dl.return_value.move_torrent = AsyncMock()
                    mock_dl.return_value.torrents_info = AsyncMock(return_value=[])
                    with patch("module.api.v1.bangumi.settings"):
                        response = client.patch("/api/v1/bangumi/update/1", json=update_data)
                    assert response.status_code == 200
                    data = response.json()
                    assert "msg_en" in data

    @pytest.mark.asyncio
    async def test_update_not_found(self, client):
        update_data = {
            "official_title": "Updated Bangumi", "title_raw": "[Group] Updated - 01",
            "season": 2, "season_raw": "S02", "group_name": "Group",
            "dpi": "1080p", "source": "WEB-DL", "subtitle": "CHT",
            "filter": "1080p", "rss_link": "https://example.com/new",
            "poster_link": "", "year": "2024", "added": False, "deleted": False,
            "eps_collect": False, "offset": 0, "rule_name": "Updated Bangumi",
            "save_path": "/downloads", "rss_id": 1,
        }
        with patch("module.api.v1.bangumi.BangumiRepository") as mock_b_cls:
            with patch("module.api.v1.bangumi.TorrentRepository"):
                with patch("module.api.v1.bangumi.create_downloader"):
                    mock_b = AsyncMock()
                    mock_b_cls.return_value = mock_b
                    mock_b.get_by_id.return_value = None
                    with patch("module.api.v1.bangumi.settings"):
                        response = client.patch("/api/v1/bangumi/update/999", json=update_data)
                    assert response.status_code == 404


class TestDeleteBangumi:

    @pytest.mark.asyncio
    async def test_delete_success(self, client):
        with patch("module.api.v1.bangumi.BangumiRepository") as mock_b_cls:
            with patch("module.api.v1.bangumi.TorrentRepository"):
                mock_b = AsyncMock()
                mock_b_cls.return_value = mock_b
                mock_b.get_by_id.return_value = _mock_bangumi_obj()
                response = client.delete("/api/v1/bangumi/delete/1", params={"file": False})
                assert response.status_code == 200
                assert "msg_en" in response.json()

    @pytest.mark.asyncio
    async def test_delete_with_files(self, client):
        with patch("module.api.v1.bangumi.BangumiRepository") as mock_b_cls:
            with patch("module.api.v1.bangumi.TorrentRepository") as mock_t_cls:
                with patch("module.api.v1.bangumi.create_downloader") as mock_dl:
                    mock_b = AsyncMock()
                    mock_b_cls.return_value = mock_b
                    mock_b.get_by_id.return_value = _mock_bangumi_obj()
                    mock_t = AsyncMock()
                    mock_t_cls.return_value = mock_t
                    dl = AsyncMock()
                    mock_dl.return_value = dl
                    dl.torrents_info = AsyncMock(return_value=[])
                    with patch("module.api.v1.bangumi.settings"):
                        response = client.delete("/api/v1/bangumi/delete/1", params={"file": True})
                    assert response.status_code == 200


class TestDeleteManyBangumi:

    @pytest.mark.asyncio
    async def test_delete_many_success(self, client):
        with patch("module.api.v1.bangumi.BangumiRepository") as mock_b_cls:
            with patch("module.api.v1.bangumi.TorrentRepository"):
                mock_b = AsyncMock()
                mock_b_cls.return_value = mock_b
                mock_b.delete_many.return_value = 3
                response = client.request("DELETE", "/api/v1/bangumi/delete", json=[1, 2, 3], params={"file": False})
                assert response.status_code == 200
                assert "msg_en" in response.json()


class TestDisableBangumi:

    @pytest.mark.asyncio
    async def test_disable_success(self, client):
        with patch("module.api.v1.bangumi.BangumiRepository") as mock_b_cls:
            with patch("module.api.v1.bangumi.TorrentRepository"):
                mock_b = AsyncMock()
                mock_b_cls.return_value = mock_b
                mock_b.get_by_id.return_value = _mock_bangumi_obj()
                response = client.delete("/api/v1/bangumi/disable/1", params={"file": False})
                assert response.status_code == 200
                assert "msg_en" in response.json()


class TestDisableManyBangumi:

    @pytest.mark.asyncio
    async def test_disable_many_success(self, client):
        with patch("module.api.v1.bangumi.BangumiRepository") as mock_b_cls:
            with patch("module.api.v1.bangumi.TorrentRepository"):
                mock_b = AsyncMock()
                mock_b_cls.return_value = mock_b
                mock_b.disable_many.return_value = 3
                response = client.request("DELETE", "/api/v1/bangumi/disable", json=[1, 2, 3], params={"file": False})
                assert response.status_code == 200
                assert "msg_en" in response.json()


class TestEnableBangumi:

    @pytest.mark.asyncio
    async def test_enable_success(self, client):
        with patch("module.api.v1.bangumi.BangumiRepository") as mock_b_cls:
            mock_b = AsyncMock()
            mock_b_cls.return_value = mock_b
            mock_b.get_by_id.return_value = _mock_bangumi_obj()
            response = client.patch("/api/v1/bangumi/enable/1")
            assert response.status_code == 200
            assert "msg_en" in response.json()


class TestResetAllBangumi:

    @pytest.mark.asyncio
    async def test_reset_all_success(self, client):
        with patch("module.api.v1.bangumi.BangumiRepository") as mock_b_cls:
            mock_b = AsyncMock()
            mock_b_cls.return_value = mock_b
            response = client.delete("/api/v1/bangumi/reset/all")
            assert response.status_code == 200
            data = response.json()
            assert data["msg_en"] == "Reset all rules successfully."
            assert data["msg_zh"] == "重置所有规则成功。"


class TestRefreshPoster:

    @pytest.mark.asyncio
    async def test_refresh_poster_all_success(self, client):
        with patch("module.api.v1.bangumi.BangumiRepository") as mock_b_cls:
            with patch("module.api.v1.bangumi.RSSRepository"):
                with patch("module.api.v1.bangumi.TorrentRepository"):
                    with patch("module.api.v1.bangumi.TitleParser"):
                        mock_b = AsyncMock()
                        mock_b_cls.return_value = mock_b
                        mock_b.get_all.return_value = []
                        response = client.post("/api/v1/bangumi/refresh/poster/all")
                        assert response.status_code == 200
                        assert "msg_en" in response.json()


class TestRefreshPosterById:

    @pytest.mark.asyncio
    async def test_refresh_poster_by_id_success(self, client):
        with patch("module.api.v1.bangumi.BangumiRepository") as mock_b_cls:
            with patch("module.api.v1.bangumi.RSSRepository") as mock_r_cls:
                with patch("module.api.v1.bangumi.TorrentRepository") as mock_t_cls:
                    with patch("module.api.v1.bangumi.TitleParser"):
                        mock_b = AsyncMock()
                        mock_b_cls.return_value = mock_b
                        mock_r = AsyncMock()
                        mock_r_cls.return_value = mock_r
                        mock_r.get_by_id.return_value = None
                        mock_t = AsyncMock()
                        mock_t_cls.return_value = mock_t
                        bangumi = _mock_bangumi_obj(poster_link="")
                        mock_b.get_by_id.return_value = bangumi
                        response = client.post("/api/v1/bangumi/refresh/poster/1")
                        assert response.status_code == 200
                        assert "msg_en" in response.json()


class TestGetTorrentStatus:

    @pytest.mark.asyncio
    async def test_get_torrent_status_success(self, client):
        with patch("module.api.v1.bangumi.TorrentRepository") as mock_t_cls:
            with patch("module.api.v1.bangumi.create_downloader") as mock_dl:
                mock_t = AsyncMock()
                mock_t_cls.return_value = mock_t
                db_torrent = MagicMock()
                db_torrent.id = 1
                db_torrent.name = "Test Episode 01"
                db_torrent.url = "https://example.com/t"
                db_torrent.downloaded = True
                db_torrent.hash = "abc123"
                mock_t.get_by_bangumi.return_value = [db_torrent]
                online = MagicMock()
                online.hash = "abc123"
                online.state = "downloading"
                online.progress = 50
                dl = AsyncMock()
                mock_dl.return_value = dl
                dl.torrents_info = AsyncMock(return_value=[online])
                with patch("module.api.v1.bangumi.settings"):
                    response = client.get("/api/v1/bangumi/torrent/1")
                assert response.status_code == 200
                data = response.json()
                assert isinstance(data, list)
                assert len(data) == 1
                assert data[0]["name"] == "Test Episode 01"


class TestDownloadTorrent:

    @pytest.mark.asyncio
    async def test_download_torrent_success(self, client):
        with patch("module.api.v1.bangumi.TorrentRepository") as mock_t_cls:
            with patch("module.api.v1.bangumi.BangumiRepository") as mock_b_cls:
                with patch("module.api.v1.bangumi.create_downloader") as mock_dl:
                    mock_t = AsyncMock()
                    mock_t_cls.return_value = mock_t
                    torrent = MagicMock()
                    torrent.id = 123
                    torrent.name = "Test Torrent"
                    torrent.url = "https://example.com/t"
                    torrent.bangumi_id = 1
                    torrent.hash = "abc"
                    torrent.downloaded = False
                    mock_t.get_by_id.return_value = torrent
                    mock_b = AsyncMock()
                    mock_b_cls.return_value = mock_b
                    bangumi = _mock_bangumi_obj()
                    mock_b.get_by_id.return_value = bangumi
                    dl = AsyncMock()
                    mock_dl.return_value = dl
                    dl.add_torrents = AsyncMock(return_value=True)
                    with patch("module.api.v1.bangumi.settings"):
                        response = client.post("/api/v1/bangumi/torrent/download", params={"torrent_id": 123})
                    assert response.status_code == 200
                    assert "msg_en" in response.json()


class TestActivatePendingBangumi:

    @pytest.mark.asyncio
    async def test_activate_success(self, client):
        with patch("module.api.v1.bangumi.BangumiRepository") as mock_b_cls:
            with patch("module.api.v1.bangumi.create_downloader") as mock_dl:
                with patch("module.api.v1.bangumi.AsyncRSSEngine") as mock_engine:
                    mock_b = AsyncMock()
                    mock_b_cls.return_value = mock_b
                    mock_b.activate_pending.return_value = (True, "Activated")
                    mock_b.get_by_id.return_value = _mock_bangumi_obj()
                    dl = AsyncMock()
                    mock_dl.return_value = dl
                    mock_engine.download_bangumi = AsyncMock(return_value={"status": True, "message": "Downloaded 3 torrents"})
                    with patch("module.api.v1.bangumi.settings"):
                        response = client.post("/api/v1/bangumi/1/activate", json={"filter": "1080p"})
                    assert response.status_code == 200
                    data = response.json()
                    assert "msg_en" in data
                    assert "activated" in data["msg_en"].lower()

    @pytest.mark.asyncio
    async def test_activate_not_pending(self, client):
        with patch("module.api.v1.bangumi.BangumiRepository") as mock_b_cls:
            mock_b = AsyncMock()
            mock_b_cls.return_value = mock_b
            mock_b.activate_pending.return_value = (False, "Bangumi not in pending review status")
            response = client.post("/api/v1/bangumi/1/activate")
            assert response.status_code == 400
            assert "msg_en" in response.json()


class TestRetriggerRename:

    @pytest.mark.asyncio
    async def test_retrigger_rename_success(self, client):
        with patch("module.api.v1.bangumi.create_downloader") as mock_dl:
            with patch("module.api.v1.bangumi.RenamerService") as mock_renamer_cls:
                dl = AsyncMock()
                mock_dl.return_value = dl
                mock_renamer = AsyncMock()
                mock_renamer_cls.return_value = mock_renamer
                mock_renamer.rename_bangumi = AsyncMock(return_value=[
                    {"torrent_id": 1, "file_count": 3},
                ])
                with patch("module.api.v1.bangumi.settings"):
                    response = client.post("/api/v1/bangumi/1/retrigger-rename")
                assert response.status_code == 200
                data = response.json()
                assert "msg_en" in data
                assert "3" in data["msg_en"]

    @pytest.mark.asyncio
    async def test_retrigger_rename_no_files(self, client):
        with patch("module.api.v1.bangumi.create_downloader") as mock_dl:
            with patch("module.api.v1.bangumi.RenamerService") as mock_renamer_cls:
                dl = AsyncMock()
                mock_dl.return_value = dl
                mock_renamer = AsyncMock()
                mock_renamer_cls.return_value = mock_renamer
                mock_renamer.rename_bangumi = AsyncMock(return_value=[])
                with patch("module.api.v1.bangumi.settings"):
                    response = client.post("/api/v1/bangumi/1/retrigger-rename")
                assert response.status_code == 200
                data = response.json()
                assert "0" in data["msg_en"]
