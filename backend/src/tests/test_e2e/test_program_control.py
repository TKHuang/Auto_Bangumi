"""E2E tests for program control endpoints."""
import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.e2e
class TestHealth:

    def test_unauthenticated_health_check(self, e2e_client):
        client, mock_dl = e2e_client
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


@pytest.mark.e2e
class TestStatus:

    def test_status_shows_running(self, authed_client):
        client, mock_dl, token = authed_client
        resp = client.get("/api/v1/status")
        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body
        assert "version" in body
        assert body["status"] is True


@pytest.mark.e2e
class TestStopStart:
    """Merged flow covering stop/start/restart transitions and their
    idempotency (formerly 6 TestStopStart + 2 TestRestart tests)."""

    def test_stop_start_restart_flow(self, authed_client):
        client, mock_dl, token = authed_client

        # Stop → status False
        resp = client.post("/api/v1/stop")
        assert resp.status_code == 200
        assert "stop" in resp.json()["msg_en"].lower()
        assert client.get("/api/v1/status").json()["status"] is False

        # Start → status True
        resp = client.post("/api/v1/start")
        assert resp.status_code == 200
        assert "start" in resp.json()["msg_en"].lower()
        assert client.get("/api/v1/status").json()["status"] is True

        # Start again — idempotent
        resp = client.post("/api/v1/start")
        assert resp.status_code == 200

        # Stop, then stop again — idempotent
        client.post("/api/v1/stop")
        resp = client.post("/api/v1/stop")
        assert resp.status_code == 200

        # Restart → status True
        resp = client.post("/api/v1/restart")
        assert resp.status_code == 200
        assert "restart" in resp.json()["msg_en"].lower()
        assert client.get("/api/v1/status").json()["status"] is True


@pytest.mark.e2e
class TestShutdown:

    def test_shutdown(self, authed_client):
        client, mock_dl, token = authed_client
        with patch("module.api.v1.program.os.kill") as mock_kill:
            resp = client.post("/api/v1/shutdown")
            assert resp.status_code == 200
            assert "shutdown" in resp.json()["msg_en"].lower()
            mock_kill.assert_called_once()


@pytest.mark.e2e
class TestProgramAuth:

    @patch("module.api.middleware.auth.VERSION", "3.0.0")
    def test_stop_requires_auth(self, e2e_client):
        client, mock_dl = e2e_client
        resp = client.post("/api/v1/stop")
        assert resp.status_code == 401
