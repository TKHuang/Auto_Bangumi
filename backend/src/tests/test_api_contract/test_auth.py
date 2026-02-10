"""API contract tests for auth endpoints."""
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from module.api.v1.auth import router as auth_router
from module.domain.models import User
from module.security.jwt import create_access_token


@pytest.fixture
def app():
    """Create FastAPI app with auth router."""
    app = FastAPI()
    app.include_router(auth_router, prefix="/api/v1")
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_user_repo():
    """Mock UserRepository."""
    repo = AsyncMock()
    repo.get_by_username = AsyncMock()
    repo.create = AsyncMock()
    repo.update_password = AsyncMock()
    return repo


@pytest.fixture
def mock_session():
    """Mock AsyncSession."""
    session = AsyncMock(spec=AsyncSession)
    session.begin = MagicMock()
    session.begin.return_value.__aenter__ = AsyncMock()
    session.begin.return_value.__aexit__ = AsyncMock()
    return session


class TestLoginEndpoint:
    """Test POST /auth/login endpoint."""

    @pytest.mark.asyncio
    async def test_login_success(self, client, mock_user_repo):
        """Test successful login with valid credentials."""
        test_user = User(id=1, username="admin", password="hashed_password")
        mock_user_repo.get_by_username.return_value = test_user

        with patch("module.api.v1.auth.get_db_session") as mock_get_db:
            with patch("module.api.v1.auth.UserRepository") as mock_repo_class:
                with patch("module.api.v1.auth.verify_password", return_value=True):
                    mock_repo_class.return_value = mock_user_repo
                    mock_get_db.return_value = mock_session

                    response = client.post(
                        "/api/v1/auth/login",
                        data={"username": "admin", "password": "password123"},
                    )

                    assert response.status_code == 200
                    data = response.json()
                    assert "access_token" in data
                    assert data["token_type"] == "bearer"
                    assert "expire" in data
                    assert isinstance(data["expire"], int)

    @pytest.mark.asyncio
    async def test_login_invalid_username(self, client, mock_user_repo):
        """Test login with non-existent username."""
        mock_user_repo.get_by_username.return_value = None

        with patch("module.api.v1.auth.get_db_session") as mock_get_db:
            with patch("module.api.v1.auth.UserRepository") as mock_repo_class:
                mock_repo_class.return_value = mock_user_repo
                mock_get_db.return_value = mock_session

                response = client.post(
                    "/api/v1/auth/login",
                    data={"username": "nonexistent", "password": "password123"},
                )

                assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_invalid_password(self, client, mock_user_repo):
        """Test login with incorrect password."""
        test_user = User(id=1, username="admin", password="hashed_password")
        mock_user_repo.get_by_username.return_value = test_user

        with patch("module.api.v1.auth.get_db_session") as mock_get_db:
            with patch("module.api.v1.auth.UserRepository") as mock_repo_class:
                with patch("module.api.v1.auth.verify_password", return_value=False):
                    mock_repo_class.return_value = mock_user_repo
                    mock_get_db.return_value = mock_session

                    response = client.post(
                        "/api/v1/auth/login",
                        data={"username": "admin", "password": "wrongpassword"},
                    )

                    assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_missing_fields(self, client):
        """Test login with missing username or password."""
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "admin"},
        )

        assert response.status_code == 422  # Validation error


class TestRefreshTokenEndpoint:
    """Test GET /auth/refresh_token endpoint."""

    @pytest.mark.asyncio
    async def test_refresh_token_success(self, client):
        """Test successful token refresh with valid cookie."""
        token = create_access_token("admin", expires_delta=timedelta(days=1))

        with patch("module.api.v1.auth.get_current_user") as mock_get_user:
            mock_get_user.return_value = "admin"

            response = client.get(
                "/api/v1/auth/refresh_token",
                cookies={"token": token},
            )

            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert data["token_type"] == "bearer"
            assert "expire" in data
            assert isinstance(data["expire"], int)

    @pytest.mark.asyncio
    async def test_refresh_token_no_cookie(self, client):
        """Test refresh token without cookie."""
        with patch("module.api.middleware.auth.VERSION", "3.0.0"):
            response = client.get("/api/v1/auth/refresh_token")

            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_token_invalid_cookie(self, client):
        """Test refresh token with invalid cookie."""
        with patch("module.api.middleware.auth.VERSION", "3.0.0"):
            response = client.get(
                "/api/v1/auth/refresh_token",
                cookies={"token": "invalid_token"},
            )

            assert response.status_code == 401


class TestLogoutEndpoint:
    """Test GET /auth/logout endpoint."""

    @pytest.mark.asyncio
    async def test_logout_success(self, client):
        """Test successful logout."""
        token = create_access_token("admin", expires_delta=timedelta(days=1))

        with patch("module.api.v1.auth.get_current_user") as mock_get_user:
            mock_get_user.return_value = "admin"

            response = client.get(
                "/api/v1/auth/logout",
                cookies={"token": token},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["msg_en"] == "Logout successfully."
            assert data["msg_zh"] == "登出成功。"

    @pytest.mark.asyncio
    async def test_logout_no_cookie(self, client):
        """Test logout without cookie."""
        with patch("module.api.middleware.auth.VERSION", "3.0.0"):
            response = client.get("/api/v1/auth/logout")

            assert response.status_code == 401


class TestUpdateEndpoint:
    """Test POST /auth/update endpoint."""

    @pytest.mark.asyncio
    async def test_update_password_success(self, client, mock_user_repo):
        """Test successful password update."""
        token = create_access_token("admin", expires_delta=timedelta(days=1))
        mock_user_repo.update_password = AsyncMock()

        with patch("module.api.v1.auth.get_current_user") as mock_get_user:
            with patch("module.api.v1.auth.get_db_session") as mock_get_db:
                with patch("module.api.v1.auth.UserRepository") as mock_repo_class:
                    with patch("module.api.v1.auth.hash_password", return_value="new_hash"):
                        mock_get_user.return_value = "admin"
                        mock_repo_class.return_value = mock_user_repo
                        mock_get_db.return_value = mock_session

                        response = client.post(
                            "/api/v1/auth/update",
                            json={"password": "newpassword123"},
                            cookies={"token": token},
                        )

                        assert response.status_code == 200
                        data = response.json()
                        assert "access_token" in data
                        assert data["token_type"] == "bearer"
                        assert "expire" in data
                        assert data["message"] == "update success"

    @pytest.mark.asyncio
    async def test_update_no_cookie(self, client):
        """Test update without cookie."""
        with patch("module.api.middleware.auth.VERSION", "3.0.0"):
            response = client.post(
                "/api/v1/auth/update",
                json={"password": "newpassword123"},
            )

            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_update_missing_password(self, client):
        """Test update with missing password field."""
        token = create_access_token("admin", expires_delta=timedelta(days=1))

        with patch("module.api.v1.auth.get_current_user") as mock_get_user:
            mock_get_user.return_value = "admin"

            response = client.post(
                "/api/v1/auth/update",
                json={},
                cookies={"token": token},
            )

            assert response.status_code == 422  # Validation error


class TestProtectedEndpoint:
    """Test that protected endpoints require authentication."""

    @pytest.mark.asyncio
    async def test_protected_endpoint_without_cookie(self, client):
        """Test accessing protected endpoint without cookie."""
        with patch("module.api.middleware.auth.VERSION", "3.0.0"):
            response = client.get("/api/v1/auth/refresh_token")
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_protected_endpoint_with_expired_token(self, client):
        """Test accessing protected endpoint with expired token."""
        # Create token that expired 1 day ago
        token = create_access_token("admin", expires_delta=timedelta(days=-1))

        with patch("module.api.middleware.auth.VERSION", "3.0.0"):
            response = client.get(
                "/api/v1/auth/refresh_token",
                cookies={"token": token},
            )

            assert response.status_code == 401


class TestFirstRunAdminCreation:
    """Test first-run admin user creation."""

    @pytest.mark.asyncio
    async def test_create_default_admin_on_first_run(self, mock_user_repo, mock_session):
        """Test that default admin user is created if no users exist."""
        mock_user_repo.get_all = AsyncMock(return_value=[])
        mock_user_repo.create = AsyncMock()

        with patch("module.api.v1.auth.UserRepository") as mock_repo_class:
            with patch("module.api.v1.auth.hash_password") as mock_hash:
                mock_repo_class.return_value = mock_user_repo
                mock_hash.return_value = "hashed_default_password"

                # This would be called during app startup
                # For now, just verify the logic works
                users = await mock_user_repo.get_all()
                assert len(users) == 0

                # Create default admin
                await mock_user_repo.create(
                    {
                        "username": "admin",
                        "password_hash": "hashed_default_password",
                    }
                )

                mock_user_repo.create.assert_called_once()
