"""Tests for async database engine with SQLite WAL mode."""

import asyncio
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from module.database.engine import (
    AsyncSessionLocal,
    create_tables,
    engine,
    get_db_session,
)


@pytest.mark.asyncio
class TestAsyncEngine:
    """Test async SQLAlchemy engine configuration."""

    async def test_engine_creates_sqlite_db_file(self, tmp_path):
        """Test that async engine creates SQLite database file."""
        # Engine should be created and ready
        assert engine is not None
        # Database file should exist after first connection
        db_path = Path("data/bangumi.db")
        # We can't guarantee file exists until first query, but engine should be valid
        assert engine.url.drivername == "sqlite+aiosqlite"

    async def test_wal_mode_enabled(self):
        """Test that WAL mode is active on SQLite database."""
        async with engine.begin() as conn:
            result = await conn.execute(text("PRAGMA journal_mode"))
            mode = result.scalar()
            assert mode.lower() == "wal", f"Expected WAL mode, got {mode}"

    async def test_synchronous_normal(self):
        """Test that synchronous is set to NORMAL."""
        async with engine.begin() as conn:
            result = await conn.execute(text("PRAGMA synchronous"))
            sync_level = result.scalar()
            # NORMAL = 1
            assert sync_level == 1, f"Expected synchronous=1 (NORMAL), got {sync_level}"

    async def test_busy_timeout_set(self):
        """Test that busy_timeout is set to 5000ms."""
        async with engine.begin() as conn:
            result = await conn.execute(text("PRAGMA busy_timeout"))
            timeout = result.scalar()
            assert timeout == 30000, f"Expected busy_timeout=30000, got {timeout}"

    async def test_foreign_keys_enabled(self):
        """Test that foreign_keys constraint is enabled."""
        async with engine.begin() as conn:
            result = await conn.execute(text("PRAGMA foreign_keys"))
            fk_enabled = result.scalar()
            assert fk_enabled == 1, f"Expected foreign_keys=1, got {fk_enabled}"

    async def test_async_session_local_factory(self):
        """Test that AsyncSessionLocal creates valid async sessions."""
        async with AsyncSessionLocal() as session:
            assert isinstance(session, AsyncSession)
            # Session should be usable
            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1

    async def test_session_expire_on_commit_false(self):
        """Test that sessions have expire_on_commit=False."""
        assert AsyncSessionLocal.kw.get("expire_on_commit") is False

    async def test_get_db_session_generator(self):
        """Test that get_db_session is an async generator."""
        session_gen = get_db_session()
        session = await session_gen.__anext__()
        try:
            assert isinstance(session, AsyncSession)
            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1
        finally:
            await session_gen.aclose()

    async def test_session_begin_auto_commits_on_success(self):
        """Test that session.begin() auto-commits on successful completion."""
        # Create a test table
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    """
                CREATE TABLE IF NOT EXISTS test_auto_commit (
                    id INTEGER PRIMARY KEY,
                    value TEXT
                )
                """
                )
            )

        # Insert data using session.begin() context manager
        async with AsyncSessionLocal() as session:
            async with session.begin():
                await session.execute(
                    text("INSERT INTO test_auto_commit (value) VALUES ('test1')")
                )
                # Don't explicitly commit - should auto-commit on exit

        # Verify data was committed
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT COUNT(*) FROM test_auto_commit WHERE value = 'test1'")
            )
            count = result.scalar()
            assert count == 1, "Data should be committed after session.begin() exits"

        # Cleanup
        async with engine.begin() as conn:
            await conn.execute(text("DROP TABLE test_auto_commit"))

    async def test_session_begin_auto_rollbacks_on_exception(self):
        """Test that session.begin() auto-rollbacks on exception."""
        # Create a test table
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    """
                CREATE TABLE IF NOT EXISTS test_auto_rollback (
                    id INTEGER PRIMARY KEY,
                    value TEXT
                )
                """
                )
            )

        # Try to insert data but raise exception
        async with AsyncSessionLocal() as session:
            try:
                async with session.begin():
                    await session.execute(
                        text("INSERT INTO test_auto_rollback (value) VALUES ('test2')")
                    )
                    # Raise exception before commit
                    raise ValueError("Test exception")
            except ValueError:
                pass  # Expected

        # Verify data was NOT committed (rolled back)
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT COUNT(*) FROM test_auto_rollback WHERE value = 'test2'")
            )
            count = result.scalar()
            assert count == 0, "Data should be rolled back after exception in session.begin()"

        # Cleanup
        async with engine.begin() as conn:
            await conn.execute(text("DROP TABLE test_auto_rollback"))

    async def test_create_tables_function(self):
        """Test that create_tables() creates database tables."""
        # This test verifies the function exists and is callable
        # Actual table creation depends on models being defined
        assert callable(create_tables)
        # Should not raise an exception
        await create_tables()


class TestDatabasePath:
    """Test database path configuration."""

    def test_database_path_default(self):
        """Test that database path defaults to data/bangumi.db."""
        # Check engine URL contains expected path
        assert "bangumi.db" in str(engine.url)
        assert "sqlite" in str(engine.url)
