import pytest
from fastapi import FastAPI, Request
from httpx import AsyncClient, ASGITransport
from starlette.middleware.base import BaseHTTPMiddleware

from zen_bangumi.api.auth import router, get_session
from zen_bangumi.services.user import create_user


def create_test_app(db_session):
    app = FastAPI()
    
    class DBSessionMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            request.state.db = db_session
            response = await call_next(request)
            return response
    
    app.add_middleware(DBSessionMiddleware)
    app.include_router(router)
    return app


@pytest.mark.asyncio
async def test_login_with_valid_credentials_returns_200_and_sets_cookie(db_session):
    await create_user("testuser", "testpass123", db_session)
    await db_session.commit()
    
    app = create_test_app(db_session)
    
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={"username": "testuser", "password": "testpass123"}
        )
    
    assert response.status_code == 200
    assert response.json()["message"] == "Login successful"
    assert response.json()["username"] == "testuser"
    assert "access_token" in response.cookies


@pytest.mark.asyncio
async def test_login_with_invalid_credentials_returns_401(db_session):
    await create_user("testuser", "correctpass", db_session)
    await db_session.commit()
    
    app = create_test_app(db_session)
    
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={"username": "testuser", "password": "wrongpass"}
        )
    
    assert response.status_code == 401
    assert "Invalid username or password" in response.json()["detail"]


@pytest.mark.asyncio
async def test_logout_clears_cookie(db_session):
    app = create_test_app(db_session)
    
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/auth/logout")
    
    assert response.status_code == 200
    assert response.json()["message"] == "Logout successful"


@pytest.mark.asyncio
async def test_refresh_token_with_valid_token_returns_200_and_new_cookie(db_session):
    await create_user("testuser", "testpass123", db_session)
    await db_session.commit()
    
    app = create_test_app(db_session)
    
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"username": "testuser", "password": "testpass123"}
        )
        
        access_token = login_response.cookies.get("access_token")
        assert access_token is not None
        
        refresh_response = await client.post(
            "/api/v1/auth/refresh",
            cookies={"access_token": access_token}
        )
    
    assert refresh_response.status_code == 200
    assert refresh_response.json()["message"] == "Token refreshed successfully"
    assert "access_token" in refresh_response.cookies


@pytest.mark.asyncio
async def test_refresh_token_without_token_returns_401(db_session):
    app = create_test_app(db_session)
    
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/auth/refresh")
    
    assert response.status_code == 401
    assert "Not authenticated" in response.json()["detail"]


@pytest.mark.asyncio
async def test_update_password_with_correct_old_password_returns_200(db_session):
    await create_user("testuser", "oldpass123", db_session)
    await db_session.commit()
    
    app = create_test_app(db_session)
    
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"username": "testuser", "password": "oldpass123"}
        )
        
        access_token = login_response.cookies.get("access_token")
        assert access_token is not None
        
        update_response = await client.put(
            "/api/v1/auth/update",
            json={"old_password": "oldpass123", "new_password": "newpass456"},
            cookies={"access_token": access_token}
        )
    
    assert update_response.status_code == 200
    assert update_response.json()["message"] == "Password updated successfully"


@pytest.mark.asyncio
async def test_update_password_with_wrong_old_password_returns_401(db_session):
    await create_user("testuser", "correctpass", db_session)
    await db_session.commit()
    
    app = create_test_app(db_session)
    
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"username": "testuser", "password": "correctpass"}
        )
        
        access_token = login_response.cookies.get("access_token")
        assert access_token is not None
        
        update_response = await client.put(
            "/api/v1/auth/update",
            json={"old_password": "wrongpass", "new_password": "newpass456"},
            cookies={"access_token": access_token}
        )
    
    assert update_response.status_code == 401
    assert "Incorrect old password" in update_response.json()["detail"]


@pytest.mark.asyncio
async def test_update_password_without_authentication_returns_401(db_session):
    app = create_test_app(db_session)
    
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.put(
            "/api/v1/auth/update",
            json={"old_password": "oldpass", "new_password": "newpass"}
        )
    
    assert response.status_code == 401
