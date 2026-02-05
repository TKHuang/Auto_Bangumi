import asyncio
import json
from pathlib import Path
from typing import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool


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
    yield engine
    await engine.dispose()


@pytest.fixture
async def async_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    async with async_engine.begin() as conn:
        pass

    async_session_local = AsyncSession(
        async_engine, expire_on_commit=False, class_=AsyncSession
    )
    yield async_session_local
    await async_session_local.close()


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
