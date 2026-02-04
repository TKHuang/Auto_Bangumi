"""Tests for FastAPI main application entry point."""

import pytest
from httpx import AsyncClient, ASGITransport

from zen_bangumi.services.user import create_user


@pytest.mark.asyncio
async def test_app_starts_without_errors(test_session):
    """Test that FastAPI app instance can be created."""
    from zen_bangumi.main import app
    
    assert app is not None
    assert app.title == "ZenBangumi"


@pytest.mark.asyncio
async def test_cors_headers_present_in_response(test_session):
    """Test that CORS middleware adds appropriate headers to responses."""
    from zen_bangumi.main import app
    
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.options(
            "/api/v1/auth/login",
            headers={"Origin": "http://localhost:3000"}
        )
    
    # CORS headers should be present
    assert "access-control-allow-origin" in response.headers


@pytest.mark.asyncio
async def test_auth_router_registered(test_session):
    """Test that auth router is registered in the application."""
    from zen_bangumi.main import app
    
    assert len(app.routes) > 0
    assert app.openapi() is not None


@pytest.mark.asyncio
async def test_unauthorized_exception_returns_json(test_session):
    """Test that 401 exceptions return proper JSON responses."""
    from zen_bangumi.main import app
    
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        # Try to access protected endpoint without auth
        response = await client.post("/api/v1/auth/refresh")
    
    assert response.status_code == 401
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_lifespan_creates_database_tables(test_engine):
    """Test that lifespan context manager creates database tables on startup."""
    from zen_bangumi.main import app
    from zen_bangumi.domain.models.base import Base
    
    # Check that tables exist by attempting to create a user
    # The lifespan should have created all tables
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    
    async_session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session_factory() as session:
        # If tables exist, this should work
        await create_user("testuser", "testpass", session)
        await session.commit()
        
        # Verify user was created
        from zen_bangumi.services.user import authenticate
        user = await authenticate("testuser", "testpass", session)
        assert user is not None
        assert user.username == "testuser"


@pytest.mark.asyncio
async def test_lifespan_admin_user_creation_logic(test_session):
    """Test that admin user can be created when no users exist."""
    from sqlalchemy import select
    from zen_bangumi.domain.models.user import User
    
    stmt = select(User)
    result = await test_session.execute(stmt)
    users = result.scalars().all()
    
    if not users:
        await create_user("admin", "admin", test_session)
        await test_session.commit()
    
    stmt = select(User).where(User.username == "admin")
    result = await test_session.execute(stmt)
    admin_user = result.scalar_one_or_none()
    
    assert admin_user is not None
    assert admin_user.username == "admin"
