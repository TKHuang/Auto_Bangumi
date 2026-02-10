"""E2E tests for program control endpoints."""
import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.e2e
class TestHealth:
    """Health check endpoint (no auth required)."""

    def test_unauthenticated_health_check(self, e2e_client):
        client, mock_dl = e2e_client
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


@pytest.mark.e2e
class TestStatus:
    """Program status endpoint."""

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
    """Stop and start the scheduler.

    We mock scheduler.stop/start to avoid APScheduler cancel scope issues
    that cause hangs in test teardown.
    """

    def test_stop(self, authed_client):
        client, mock_dl, token = authed_client
        with patch("module.scheduler.engine.AsyncScheduler.stop", new_callable=AsyncMock):
            resp = client.post("/api/v1/stop")
            assert resp.status_code == 200
            assert "stop" in resp.json()["msg_en"].lower()

    def test_start_after_stop(self, authed_client):
        client, mock_dl, token = authed_client
        with patch("module.scheduler.engine.AsyncScheduler.stop", new_callable=AsyncMock):
            stop_resp = client.post("/api/v1/stop")
            assert stop_resp.status_code == 200

        with patch("module.scheduler.engine.AsyncScheduler.start", new_callable=AsyncMock):
            start_resp = client.post("/api/v1/start")
            assert start_resp.status_code == 200
            assert "start" in start_resp.json()["msg_en"].lower()

    def test_idempotent_start(self, authed_client):
        client, mock_dl, token = authed_client
        # Scheduler is already running after app startup
        resp = client.post("/api/v1/start")
        assert resp.status_code == 200

    def test_idempotent_stop(self, authed_client):
        client, mock_dl, token = authed_client
        with patch("module.scheduler.engine.AsyncScheduler.stop", new_callable=AsyncMock):
            client.post("/api/v1/stop")
            resp = client.post("/api/v1/stop")
            assert resp.status_code == 200


@pytest.mark.e2e
class TestRestart:
    """Restart the scheduler."""

    def test_restart_roundtrip(self, authed_client):
        client, mock_dl, token = authed_client
        with patch("module.scheduler.engine.AsyncScheduler.stop", new_callable=AsyncMock):
            with patch("module.scheduler.engine.AsyncScheduler.start", new_callable=AsyncMock):
                resp = client.post("/api/v1/restart")
                assert resp.status_code == 200
                assert "restart" in resp.json()["msg_en"].lower()


@pytest.mark.e2e
class TestShutdown:
    """Shutdown endpoint (sends SIGINT to the process)."""

    def test_shutdown(self, authed_client):
        client, mock_dl, token = authed_client
        with patch("module.api.v1.program.os.kill") as mock_kill:
            resp = client.post("/api/v1/shutdown")
            assert resp.status_code == 200
            assert "shutdown" in resp.json()["msg_en"].lower()
            mock_kill.assert_called_once()


@pytest.mark.e2e
class TestProgramAuth:
    """Verify program endpoints require authentication."""

    @patch("module.api.middleware.auth.VERSION", "3.0.0")
    def test_stop_requires_auth(self, e2e_client):
        client, mock_dl = e2e_client
        # No login, no cookie
        resp = client.post("/api/v1/stop")
        assert resp.status_code == 401
