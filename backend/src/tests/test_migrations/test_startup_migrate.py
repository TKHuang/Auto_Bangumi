"""Tests for startup migration helper (is_pre_alembic_db, run_migrations)."""
from pathlib import Path

import pytest
import sqlalchemy as sa

from module.database.migrate import is_pre_alembic_db


@pytest.mark.unit
def test_is_pre_alembic_db_returns_false_for_nonexistent_db(tmp_path):
    """Missing DB file is a fresh install, not pre-Alembic."""
    nonexistent = tmp_path / "nope.db"
    assert is_pre_alembic_db(nonexistent) is False


@pytest.mark.unit
def test_is_pre_alembic_db_returns_false_for_empty_db(tmp_path):
    """Empty DB file (no tables) is fresh, not pre-Alembic."""
    db = tmp_path / "empty.db"
    engine = sa.create_engine(f"sqlite:///{db}")
    with engine.connect():
        pass  # Just create the file
    assert is_pre_alembic_db(db) is False


@pytest.mark.unit
def test_is_pre_alembic_db_returns_true_for_legacy_schema(tmp_path):
    """DB with bangumi table but no alembic_version table -> pre-Alembic."""
    db = tmp_path / "legacy.db"
    engine = sa.create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE bangumi (id INTEGER PRIMARY KEY)"))
    assert is_pre_alembic_db(db) is True


@pytest.mark.unit
def test_is_pre_alembic_db_returns_false_when_alembic_version_exists(tmp_path):
    """DB with alembic_version is already managed."""
    db = tmp_path / "managed.db"
    engine = sa.create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE bangumi (id INTEGER PRIMARY KEY)"))
        conn.execute(sa.text("CREATE TABLE alembic_version (version_num TEXT NOT NULL)"))
    assert is_pre_alembic_db(db) is False
