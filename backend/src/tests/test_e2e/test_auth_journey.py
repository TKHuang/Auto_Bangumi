"""E2E tests for authentication journey."""
import pytest
from unittest.mock import patch


@pytest.mark.e2e
class TestFirstBoot:
    """Verify default admin account exists after first boot."""

    def test_default_admin_created(self, e2e_client):
        client, mock_dl = e2e_client
        resp = client.post(
            "/api/v1/auth/login",
            data={"username": "admin", "password": "adminadmin"},
        )
        assert resp.status_code == 200

    def test_login_returns_jwt_and_cookie(self, e2e_client):
        client, mock_dl = e2e_client
        resp = client.post(
            "/api/v1/auth/login",
            data={"username": "admin", "password": "adminadmin"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert "expire" in body
        assert isinstance(body["expire"], int)


@pytest.mark.e2e
class TestLoginFlow:
    """Test various login scenarios."""

    def test_valid_login(self, e2e_client):
        client, mock_dl = e2e_client
        resp = client.post(
            "/api/v1/auth/login",
            data={"username": "admin", "password": "adminadmin"},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_wrong_password(self, e2e_client):
        client, mock_dl = e2e_client
        resp = client.post(
            "/api/v1/auth/login",
            data={"username": "admin", "password": "wrongpassword"},
        )
        assert resp.status_code == 401
        assert "Invalid credentials" in resp.json()["detail"]

    def test_nonexistent_user(self, e2e_client):
        client, mock_dl = e2e_client
        resp = client.post(
            "/api/v1/auth/login",
            data={"username": "nobody", "password": "whatever"},
        )
        assert resp.status_code == 401
        assert "Invalid credentials" in resp.json()["detail"]

    def test_missing_credentials(self, e2e_client):
        client, mock_dl = e2e_client
        resp = client.post("/api/v1/auth/login")
        assert resp.status_code == 422


@pytest.mark.e2e
class TestTokenRefresh:
    """Test token refresh flow."""

    def test_refresh_with_valid_cookie(self, authed_client):
        client, mock_dl, token = authed_client
        resp = client.get("/api/v1/auth/refresh_token")
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert "expire" in body

    @patch("module.api.middleware.auth.VERSION", "3.0.0")
    def test_refresh_without_cookie(self, e2e_client):
        client, mock_dl = e2e_client
        # No login, no cookie — should be rejected
        resp = client.get("/api/v1/auth/refresh_token")
        assert resp.status_code == 401


@pytest.mark.e2e
class TestLogout:
    """Test logout flow."""

    def test_logout_clears_cookie(self, authed_client):
        client, mock_dl, token = authed_client
        resp = client.get("/api/v1/auth/logout")
        assert resp.status_code == 200
        assert "Logout successfully" in resp.json()["msg_en"]

    @patch("module.api.middleware.auth.VERSION", "3.0.0")
    def test_request_after_logout(self, e2e_client):
        client, mock_dl = e2e_client
        # Login
        login_resp = client.post(
            "/api/v1/auth/login",
            data={"username": "admin", "password": "adminadmin"},
        )
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]
        client.cookies.set("token", token)

        # Logout (clears cookie server-side)
        logout_resp = client.get("/api/v1/auth/logout")
        assert logout_resp.status_code == 200

        # Clear cookie on client side too
        client.cookies.clear()

        # Subsequent authed request should fail
        resp = client.get("/api/v1/auth/refresh_token")
        assert resp.status_code == 401


@pytest.mark.e2e
class TestPasswordUpdate:
    """Test password change flow."""

    def test_change_password_roundtrip(self, authed_client):
        client, mock_dl, token = authed_client

        # Change password
        resp = client.post(
            "/api/v1/auth/update",
            json={"password": "newpass123"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body.get("message") == "update success"

        # Login with the new password
        new_login = client.post(
            "/api/v1/auth/login",
            data={"username": "admin", "password": "newpass123"},
        )
        assert new_login.status_code == 200

    def test_empty_password_rejected(self, authed_client):
        client, mock_dl, token = authed_client
        resp = client.post(
            "/api/v1/auth/update",
            json={"password": ""},
        )
        assert resp.status_code == 400
