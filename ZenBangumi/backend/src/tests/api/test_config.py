from pathlib import Path

import pytest
from httpx import AsyncClient

from zen_bangumi.config.loader import ConfigLoader


@pytest.fixture(autouse=True)
def clean_config():
    config_file = Path("data/config.json")
    if config_file.exists():
        config_file.unlink()
    yield
    if config_file.exists():
        config_file.unlink()


@pytest.mark.asyncio
async def test_get_config_returns_full_config(client: AsyncClient):
    response = await client.get("/api/v1/config/")
    assert response.status_code == 200
    data = response.json()
    
    assert "program" in data
    assert "downloader" in data
    assert "rss_parser" in data
    assert "bangumi_manage" in data
    assert "log" in data
    assert "proxy" in data
    assert "notification" in data
    
    assert data["program"]["webui_port"] == 7892
    assert data["downloader"]["type"] == "qbittorrent"


@pytest.mark.asyncio
async def test_update_config_partial_update_only_provided_fields(client: AsyncClient):
    partial_update = {
        "program": {"webui_port": 9999},
    }
    
    response = await client.put("/api/v1/config/", json=partial_update)
    assert response.status_code == 200
    data = response.json()
    
    assert data["program"]["webui_port"] == 9999
    assert data["program"]["rss_time"] == 900
    
    assert data["downloader"]["type"] == "qbittorrent"


@pytest.mark.asyncio
async def test_update_config_multiple_sections(client: AsyncClient):
    update = {
        "program": {"rss_time": 600},
        "downloader": {"path": "/new/path"},
    }
    
    response = await client.put("/api/v1/config/", json=update)
    assert response.status_code == 200
    data = response.json()
    
    assert data["program"]["rss_time"] == 600
    assert data["downloader"]["path"] == "/new/path"


@pytest.mark.asyncio
async def test_config_endpoints_require_auth(client_no_auth: AsyncClient):
    response = await client_no_auth.get("/api/v1/config/")
    assert response.status_code == 401
    
    response = await client_no_auth.put(
        "/api/v1/config/", json={"program": {"webui_port": 8888}}
    )
    assert response.status_code == 401
