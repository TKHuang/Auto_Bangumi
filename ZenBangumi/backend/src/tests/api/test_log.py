from pathlib import Path

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_logs_returns_empty_when_no_log_file(client: AsyncClient, tmp_path):
    log_file = tmp_path / "log.txt"
    
    response = await client.get("/api/v1/log/")
    assert response.status_code == 200
    data = response.json()
    assert "logs" in data


@pytest.mark.asyncio
async def test_get_logs_returns_content(client: AsyncClient, tmp_path):
    log_file = Path("data/log.txt")
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    log_content = "\n".join([f"Log line {i}" for i in range(10)])
    log_file.write_text(log_content, encoding="utf-8")
    
    response = await client.get("/api/v1/log/")
    assert response.status_code == 200
    data = response.json()
    assert "logs" in data
    
    log_file.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_delete_logs_clears_file(client: AsyncClient):
    log_file = Path("data/log.txt")
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text("Test log content", encoding="utf-8")
    
    response = await client.delete("/api/v1/log/")
    assert response.status_code == 200
    assert "cleared successfully" in response.json()["message"].lower()
    
    if log_file.exists():
        content = log_file.read_text(encoding="utf-8")
        assert content == ""


@pytest.mark.asyncio
async def test_log_endpoints_require_auth(client_no_auth: AsyncClient):
    response = await client_no_auth.get("/api/v1/log/")
    assert response.status_code == 401
    
    response = await client_no_auth.delete("/api/v1/log/")
    assert response.status_code == 401
