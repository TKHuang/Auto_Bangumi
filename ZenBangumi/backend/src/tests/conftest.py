"""
Pytest configuration and shared fixtures for ZenBangumi tests.

Provides:
- Async SQLite test engine (in-memory)
- Async session factory
- FastAPI TestClient with async support
- Test configuration
"""

import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from httpx import AsyncClient

from zen_bangumi.domain.models.base import Base


@pytest_asyncio.fixture
async def test_engine():
    """
    Create an in-memory SQLite async engine for testing.
    
    Uses sqlite+aiosqlite:// for async support.
    WAL mode is not applicable to in-memory databases.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Cleanup
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_engine):
    """
    Create an async session for database operations in tests.
    
    Each test gets a fresh session connected to the in-memory test database.
    """
    async_session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    session = async_session_factory()
    try:
        yield session
    finally:
        await session.close()


@pytest_asyncio.fixture
async def test_client(test_engine):
    """
    Create a FastAPI TestClient with async support using httpx.AsyncClient.
    
    This fixture is prepared for future use when FastAPI app is created.
    Currently returns a basic AsyncClient for testing async HTTP operations.
    """
    client = AsyncClient(base_url="http://test")
    try:
        yield client
    finally:
        await client.aclose()


@pytest.fixture
def test_config():
    """
    Provide a test configuration object.
    
    Returns a dict with default test settings.
    Can be extended as config models are created.
    """
    return {
        "debug": True,
        "database_url": "sqlite+aiosqlite:///:memory:",
        "api_port": 8000,
    }


@pytest.fixture
def event_loop():
    """
    Create an event loop for async tests.
    
    pytest-asyncio uses this to run async fixtures and tests.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
