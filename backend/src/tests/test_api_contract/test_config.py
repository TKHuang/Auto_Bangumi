"""Tests for config API endpoints."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from module.api.v1.config import router
from module.conf.models import Config, Program, Downloader, RSSParser, BangumiManage, Log, Proxy, Notification, ExperimentalOpenAI
from fastapi import FastAPI


@pytest.fixture
def app():
    """Create FastAPI app with config router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_config():
    """Create mock config object."""
    return Config(
        program=Program(rss_time=900, rename_time=60, webui_port=7892),
        downloader=Downloader(
            type="qbittorrent",
            host_="172.17.0.1:8080",
            username_="admin",
            password_="adminadmin",
            path="/downloads/Bangumi",
            ssl=False,
        ),
        rss_parser=RSSParser(
            enable=True,
            filter=["720", r"\d+-\d"],
            language="zh",
        ),
        bangumi_manage=BangumiManage(
            enable=True,
            eps_complete=False,
            eps_complete_from_source=True,
            rename_method="pn",
            group_tag=False,
            remove_bad_torrent=False,
        ),
        log=Log(debug_enable=False),
        proxy=Proxy(
            enable=False,
            type="http",
            host="",
            port=0,
            username_="",
            password_="",
        ),
        notification=Notification(
            enable=False,
            type="telegram",
            token_="",
            chat_id_="",
        ),
        experimental_openai=ExperimentalOpenAI(
            enable=False,
            api_key="",
            api_base="https://api.openai.com/v1",
            api_type="openai",
            api_version="2023-05-15",
            model="gpt-3.5-turbo",
            deployment_id="",
        ),
    )


@pytest.mark.parametrize(
    "method,path,auth_mode",
    [
        ("get", "/config/get", "missing"),
        ("get", "/config/get", "invalid"),
        ("patch", "/config/update", "missing"),
        ("patch", "/config/update", "invalid"),
    ],
    ids=["get_no_auth", "get_invalid_token", "patch_no_auth", "patch_invalid_token"],
)
def test_config_endpoints_reject_missing_or_invalid_token(client, mock_config, method, path, auth_mode):
    kwargs = {}
    if method == "patch":
        kwargs["json"] = mock_config.model_dump(by_alias=True)

    with patch("module.api.middleware.auth.VERSION", "3.0.0"):
        if auth_mode == "invalid":
            with patch("module.api.middleware.auth.decode_access_token") as mock_decode:
                mock_decode.side_effect = Exception("Invalid token")
                response = getattr(client, method)(path, cookies={"token": "invalid_token"}, **kwargs)
        else:
            response = getattr(client, method)(path, **kwargs)

    assert response.status_code == 401


class TestGetConfig:
    """Tests for GET /config/get endpoint."""

    def test_get_config_with_auth(self, client, mock_config):
        """Test GET /config/get with valid token returns full config."""
        with patch("module.api.middleware.auth.decode_access_token") as mock_decode:
            mock_decode.return_value = {"sub": "testuser"}
            
            with patch("module.api.v1.config.settings", mock_config):
                response = client.get("/config/get", cookies={"token": "valid_token"})
                
                assert response.status_code == 200
                data = response.json()
                
                # Verify all config sections present
                assert "program" in data
                assert "downloader" in data
                assert "rss_parser" in data
                assert "bangumi_manage" in data
                assert "log" in data
                assert "proxy" in data
                assert "notification" in data
                assert "experimental_openai" in data
                
                # Verify program section
                assert data["program"]["rss_time"] == 900
                assert data["program"]["rename_time"] == 60
                assert data["program"]["webui_port"] == 7892
                
                # Verify downloader section (with aliases)
                assert data["downloader"]["type"] == "qbittorrent"
                assert data["downloader"]["host"] == "172.17.0.1:8080"
                assert data["downloader"]["username"] == "admin"
                assert data["downloader"]["password"] == "adminadmin"
                assert data["downloader"]["path"] == "/downloads/Bangumi"
                assert data["downloader"]["ssl"] is False

class TestUpdateConfig:
    """Tests for PATCH /config/update endpoint."""

    def test_update_config_success(self, client, mock_config):
        """Test PATCH /config/update with valid token saves config."""
        with patch("module.api.middleware.auth.decode_access_token") as mock_decode:
            mock_decode.return_value = {"sub": "testuser"}
            
            mock_settings = MagicMock()
            mock_settings.save = MagicMock()
            mock_settings.load = MagicMock()
            
            with patch("module.api.v1.config.settings", mock_settings):
                response = client.patch(
                    "/config/update",
                    json=mock_config.model_dump(by_alias=True),
                    cookies={"token": "valid_token"},
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["msg_en"] == "Update config successfully."
                assert data["msg_zh"] == "更新配置成功。"
                
                # Verify save and load were called
                mock_settings.save.assert_called_once()
                mock_settings.load.assert_called_once()

    def test_update_config_save_failure(self, client, mock_config):
        """Test PATCH /config/update handles save failure gracefully."""
        with patch("module.api.middleware.auth.decode_access_token") as mock_decode:
            mock_decode.return_value = {"sub": "testuser"}
            
            mock_settings = MagicMock()
            mock_settings.save = MagicMock(side_effect=Exception("Save failed"))
            
            with patch("module.api.v1.config.settings", mock_settings):
                response = client.patch(
                    "/config/update",
                    json=mock_config.model_dump(by_alias=True),
                    cookies={"token": "valid_token"},
                )
                
                assert response.status_code == 500
                data = response.json()
                assert data["msg_en"] == "Update config failed."
                assert data["msg_zh"] == "更新配置失败。"

    def test_update_config_uses_by_alias(self, client, mock_config):
        """Test PATCH /config/update uses by_alias=True for serialization."""
        with patch("module.api.middleware.auth.decode_access_token") as mock_decode:
            mock_decode.return_value = {"sub": "testuser"}
            
            mock_settings = MagicMock()
            mock_settings.save = MagicMock()
            mock_settings.load = MagicMock()
            
            with patch("module.api.v1.config.settings", mock_settings):
                response = client.patch(
                    "/config/update",
                    json=mock_config.model_dump(by_alias=True),
                    cookies={"token": "valid_token"},
                )
                
                assert response.status_code == 200
                
                # Verify save was called with by_alias=True format
                call_args = mock_settings.save.call_args
                saved_config = call_args.kwargs.get("config_dict")
                
                # Check that aliases are used (e.g., "host" not "host_")
                assert "host" in saved_config["downloader"]
                assert "username" in saved_config["downloader"]
                assert "password" in saved_config["downloader"]


@pytest.mark.anyio
async def test_reschedule_preserves_stopped_scheduler():
    """Saving config must keep a stopped program stopped."""
    with patch("module.api.v1.program.get_scheduler") as get_scheduler:
        with patch(
            "module.api.v1.program._has_active_schedules",
            new_callable=AsyncMock,
        ) as has_active_schedules:
            with patch(
                "module.api.v1.program._remove_all_schedules",
                new_callable=AsyncMock,
            ) as remove_all_schedules:
                with patch(
                    "module.api.v1.program._add_all_schedules",
                    new_callable=AsyncMock,
                ) as add_all_schedules:
                    get_scheduler.return_value = object()
                    has_active_schedules.return_value = False

                    from module.api.v1.config import _reschedule_jobs_with_current_config

                    await _reschedule_jobs_with_current_config()

    has_active_schedules.assert_awaited_once()
    remove_all_schedules.assert_not_awaited()
    add_all_schedules.assert_not_awaited()
