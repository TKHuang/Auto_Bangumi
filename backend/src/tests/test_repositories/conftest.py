"""Shared fixtures for repository-layer tests.

Each test gets an isolated SQLite DB created via Base.metadata.create_all
(not Alembic — that path is covered by test_migrations/). The DB lives in a
tmp_path so parallel tests never collide.
"""
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

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


@pytest_asyncio.fixture
async def db_session(tmp_path):
    db_file = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session
    await engine.dispose()
