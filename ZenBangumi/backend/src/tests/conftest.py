import asyncio
from datetime import timedelta
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from zen_bangumi.api.auth import router as auth_router
from zen_bangumi.api.bangumi import router as bangumi_router
from zen_bangumi.api.config import router as config_router
from zen_bangumi.api.log import router as log_router
from zen_bangumi.api.program import router as program_router
from zen_bangumi.api.rss import router as rss_router
from zen_bangumi.api.search import router as search_router
from zen_bangumi.domain.models.base import Base
from zen_bangumi.domain.models.user import User
from zen_bangumi.services.auth import create_access_token
from zen_bangumi.services.user import create_user


@pytest_asyncio.fixture
async def test_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
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
async def test_user(db_session: AsyncSession) -> User:
    user = await create_user("testuser", "testpass", db_session)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_app(test_engine):
    app = FastAPI()
    
    async def get_test_db():
        async_session_factory = async_sessionmaker(
            test_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with async_session_factory() as session:
            yield session
    
    from starlette.middleware.base import BaseHTTPMiddleware
    
    class TestDBSessionMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            async_session_factory = async_sessionmaker(
                test_engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
            async with async_session_factory() as session:
                request.state.db = session
                response = await call_next(request)
            return response
    
    app.add_middleware(TestDBSessionMiddleware)
    app.include_router(auth_router)
    app.include_router(bangumi_router)
    app.include_router(config_router)
    app.include_router(log_router)
    app.include_router(program_router)
    app.include_router(rss_router)
    app.include_router(search_router)
    
    return app


@pytest_asyncio.fixture
async def client(test_app: FastAPI, test_user: User):
    token = create_access_token(test_user.id, timedelta(hours=1))
    
    transport = ASGITransport(app=test_app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={"access_token": token},
    ) as client:
        yield client


@pytest_asyncio.fixture
async def client_no_auth(test_app: FastAPI):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        yield client


@pytest.fixture
def test_config():
    return {
        "debug": True,
        "database_url": "sqlite+aiosqlite:///:memory:",
        "api_port": 8000,
    }


@pytest.fixture
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
