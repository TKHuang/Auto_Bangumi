import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_check_health_returns_200(client: AsyncClient):
    response = await client.get("/api/v1/program/check")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "OK"


@pytest.mark.asyncio
async def test_get_status_not_implemented(client: AsyncClient):
    response = await client.get("/api/v1/program/status")
    assert response.status_code == 501
    assert "not yet implemented" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_start_scheduler_not_implemented(client: AsyncClient):
    response = await client.post("/api/v1/program/start")
    assert response.status_code == 501
    assert "not yet implemented" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_stop_scheduler_not_implemented(client: AsyncClient):
    response = await client.post("/api/v1/program/stop")
    assert response.status_code == 501
    assert "not yet implemented" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_restart_scheduler_not_implemented(client: AsyncClient):
    response = await client.post("/api/v1/program/restart")
    assert response.status_code == 501
    assert "not yet implemented" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_shutdown_not_implemented(client: AsyncClient):
    response = await client.post("/api/v1/program/shutdown")
    assert response.status_code == 501
    assert "not yet implemented" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_program_endpoints_require_auth(client_no_auth: AsyncClient):
    endpoints = [
        ("GET", "/api/v1/program/check"),
        ("GET", "/api/v1/program/status"),
        ("POST", "/api/v1/program/start"),
        ("POST", "/api/v1/program/stop"),
        ("POST", "/api/v1/program/restart"),
        ("POST", "/api/v1/program/shutdown"),
    ]
    
    for method, path in endpoints:
        if method == "GET":
            response = await client_no_auth.get(path)
        elif method == "POST":
            response = await client_no_auth.post(path)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        assert response.status_code == 401, f"Expected 401 for {method} {path}"
