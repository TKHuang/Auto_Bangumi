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

    def test_stop(self, authed_client):
        client, mock_dl, token = authed_client
        resp = client.post("/api/v1/stop")
        assert resp.status_code == 200
        assert "stop" in resp.json()["msg_en"].lower()

    def test_start_after_stop(self, authed_client):
        client, mock_dl, token = authed_client
        stop_resp = client.post("/api/v1/stop")
        assert stop_resp.status_code == 200

        start_resp = client.post("/api/v1/start")
        assert start_resp.status_code == 200
        assert "start" in start_resp.json()["msg_en"].lower()

    def test_idempotent_start(self, authed_client):
        client, mock_dl, token = authed_client
        resp = client.post("/api/v1/start")
        assert resp.status_code == 200

    def test_idempotent_stop(self, authed_client):
        client, mock_dl, token = authed_client
        client.post("/api/v1/stop")
        resp = client.post("/api/v1/stop")
        assert resp.status_code == 200

    def test_status_false_after_stop(self, authed_client):
        client, mock_dl, token = authed_client
        client.post("/api/v1/stop")
        resp = client.get("/api/v1/status")
        assert resp.json()["status"] is False

    def test_status_true_after_start(self, authed_client):
        client, mock_dl, token = authed_client
        client.post("/api/v1/stop")
        client.post("/api/v1/start")
        resp = client.get("/api/v1/status")
        assert resp.json()["status"] is True


@pytest.mark.e2e
class TestRestart:

    def test_restart_roundtrip(self, authed_client):
        client, mock_dl, token = authed_client
        resp = client.post("/api/v1/restart")
        assert resp.status_code == 200
        assert "restart" in resp.json()["msg_en"].lower()

    def test_status_true_after_restart(self, authed_client):
        client, mock_dl, token = authed_client
        client.post("/api/v1/restart")
        resp = client.get("/api/v1/status")
        assert resp.json()["status"] is True


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
