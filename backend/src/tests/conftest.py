import asyncio
import json
from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from module.domain.models.base import Base

# Import every model module so its __tablename__ registers with Base.metadata.
import module.domain.models.user  # noqa: F401
import module.domain.models.rss  # noqa: F401
import module.domain.models.bangumi  # noqa: F401
import module.domain.models.torrent  # noqa: F401
import module.domain.models.series  # noqa: F401
import module.domain.models.mikan_ref  # noqa: F401
import module.domain.models.pending_enrichment  # noqa: F401
import module.domain.models.merge_history  # noqa: F401


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def async_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def async_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    async_session_local = AsyncSession(async_engine, expire_on_commit=False)
    yield async_session_local
    await async_session_local.close()


@pytest_asyncio.fixture
async def db_session(tmp_path):
    """Isolated SQLite DB per test. Used by repository and mikan tests."""
    db_file = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session
    await engine.dispose()


@pytest.fixture
def test_config():
    config_path = Path(__file__).parent / "fixtures" / "config_test.json"
    with open(config_path) as f:
        return json.load(f)


@pytest.fixture
def search_provider_config():
    config_path = Path(__file__).parent / "fixtures" / "search_provider.json"
    with open(config_path) as f:
        return json.load(f)


@pytest.fixture
def fixtures_dir():
    """Return the path to the test fixtures directory."""
    return Path(__file__).parent / "fixtures"
