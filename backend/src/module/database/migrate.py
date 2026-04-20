"""Startup database migration helpers.

Bridges the pre-Alembic era (schema managed by main.py:_run_migrations) and
the Alembic-managed era. On first startup after upgrade:
  - Fresh DB -> Alembic upgrades from scratch, creating everything.
  - Legacy DB (schema present, no alembic_version) -> Alembic stamps baseline,
    then upgrades any later revisions.
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

import sqlalchemy as sa

from alembic import command as alembic_cmd
from alembic.config import Config as AlembicConfig

logger = logging.getLogger(__name__)

_LEGACY_MARKER_TABLES = ("bangumi", "rssitem", "torrent", "user")

BASELINE_REVISION = "0001_baseline"


def is_pre_alembic_db(db_path: Path) -> bool:
    """Return True iff DB has legacy schema but no alembic_version table.

    Detection rule:
      - If DB file doesn't exist -> False (fresh install).
      - If DB file exists but has no legacy tables -> False (empty).
      - If DB has any legacy table AND lacks alembic_version -> True.
      - Otherwise -> False.
    """
    if not db_path.exists():
        return False

    sync_url = f"sqlite:///{db_path}"
    engine = sa.create_engine(sync_url)
    try:
        inspector = sa.inspect(engine)
        tables = set(inspector.get_table_names())
    finally:
        engine.dispose()

    has_legacy = bool(set(_LEGACY_MARKER_TABLES) & tables)
    has_alembic = "alembic_version" in tables
    return has_legacy and not has_alembic


def _backend_dir() -> Path:
    """Resolve the backend/ directory (where alembic.ini lives).

    Honors AB_BACKEND_DIR when set, which is required for Docker dev where
    backend/src is mounted as /app and the default walk-up would land on
    "/". Otherwise walks up 4 levels from this file at
    backend/src/module/database/migrate.py.
    """
    override = os.getenv("AB_BACKEND_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent.parent.parent


def _alembic_config() -> AlembicConfig:
    """Build an AlembicConfig pointing at the project's alembic.ini.

    DB URL comes from env.py (honors AB_ALEMBIC_DB_URL override), so we do not
    set sqlalchemy.url here.
    """
    ini_path = _backend_dir() / "alembic.ini"
    cfg = AlembicConfig(str(ini_path))
    cfg.set_main_option("script_location", str(_backend_dir() / "alembic"))
    return cfg


def _resolve_db_path(override: Optional[Path]) -> Path:
    if override is not None:
        return override
    url = os.getenv("AB_ALEMBIC_DB_URL")
    if url and ":///" in url:
        return Path(url.split(":///", 1)[1])
    # Default path mirrors module.database.engine.DB_PATH (relative to CWD).
    return Path("data") / "bangumi.db"


async def run_migrations(db_path_override: Optional[Path] = None) -> None:
    """Ensure DB schema is up-to-date with the latest Alembic revision.

    Flow:
      1. Determine the DB path (honors AB_ALEMBIC_DB_URL env var for tests).
      2. If DB is pre-Alembic (legacy schema, no alembic_version) -> stamp baseline.
      3. Run `alembic upgrade head`.

    Alembic commands are sync and invoke their own asyncio.run() via env.py's
    online mode. Wrap with asyncio.to_thread so this coroutine stays non-blocking
    inside the FastAPI lifespan event loop.
    """
    db_path = _resolve_db_path(db_path_override)

    if is_pre_alembic_db(db_path):
        logger.info(
            "Pre-Alembic DB detected at %s; stamping baseline %s",
            db_path, BASELINE_REVISION,
        )
        await asyncio.to_thread(alembic_cmd.stamp, _alembic_config(), BASELINE_REVISION)

    logger.info("Running alembic upgrade head on %s", db_path)
    await asyncio.to_thread(alembic_cmd.upgrade, _alembic_config(), "head")
    logger.info("Alembic migrations complete")
