"""Alembic async migration environment for Auto_Bangumi.

Uses the project's existing AsyncEngine from module.database.engine to ensure
the same SQLite PRAGMAs (WAL, foreign_keys, busy_timeout) are applied.
"""
import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine

from alembic import context

# Make `module.*` importable when running `alembic` from backend/
BACKEND_SRC = Path(__file__).resolve().parent.parent / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from module.database.engine import DATABASE_URL, engine as project_engine  # noqa: E402
from module.domain.models.base import Base  # noqa: E402
# Import all model modules so their tables register with Base.metadata
import module.domain.models.user  # noqa: F401, E402
import module.domain.models.rss  # noqa: F401, E402
import module.domain.models.bangumi  # noqa: F401, E402
import module.domain.models.torrent  # noqa: F401, E402
import module.domain.models.series  # noqa: F401, E402

config = context.config

_db_url = os.getenv("AB_ALEMBIC_DB_URL", DATABASE_URL)
config.set_main_option("sqlalchemy.url", _db_url)

# If env var override is set, rebuild an engine pointing at the override URL
# so online mode targets the test/scratch DB instead of the default.
if os.getenv("AB_ALEMBIC_DB_URL"):
    from sqlalchemy.ext.asyncio import create_async_engine
    project_engine = create_async_engine(_db_url, future=True)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _include_object(obj, name, type_, reflected, compare_to):
    """Exclude objects managed outside SQLAlchemy metadata.

    idx_torrent_hash_bangumi is a partial unique index created via op.execute()
    in 0001_baseline because SQLAlchemy metadata cannot express the WHERE clause.
    Exclude it from autogenerate diffs so subsequent revisions stay clean.
    Similarly for uq_series_fallback_null_cour added in 0002_add_series.
    """
    if type_ == "index" and name in (
        "idx_torrent_hash_bangumi",
        "uq_series_fallback_null_cour",
    ):
        return False
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (URL only, no engine)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # SQLite batch mode for ALTER support
        include_object=_include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,  # SQLite batch mode
        include_object=_include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations using the project's AsyncEngine."""
    connectable: AsyncEngine = project_engine
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
