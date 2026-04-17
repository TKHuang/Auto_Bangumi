"""Startup database migration helpers.

Bridges the pre-Alembic era (schema managed by main.py:_run_migrations) and
the Alembic-managed era. On first startup after upgrade:
  - Fresh DB -> Alembic upgrades from scratch, creating everything.
  - Legacy DB (schema present, no alembic_version) -> Alembic stamps baseline,
    then upgrades any later revisions.
"""
from __future__ import annotations

import logging
from pathlib import Path

import sqlalchemy as sa

logger = logging.getLogger(__name__)

_LEGACY_MARKER_TABLES = ("bangumi", "rssitem", "torrent", "user")


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
