"""Tests for migration 0009: bangumi.mikan_bangumi_url column + partial unique."""
import os
import subprocess
from pathlib import Path

import pytest
import sqlalchemy as sa

BACKEND_DIR = Path(__file__).parent.parent.parent


def _run_alembic(target: str, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["uv", "run", "alembic", "-c", str(BACKEND_DIR / "alembic.ini"), "upgrade", target],
        cwd=BACKEND_DIR, env=env, capture_output=True, text=True,
    )


def _bangumi_columns(db: Path) -> set[str]:
    engine = sa.create_engine(f"sqlite:///{db}")
    try:
        inspector = sa.inspect(engine)
        return {c["name"] for c in inspector.get_columns("bangumi")}
    finally:
        engine.dispose()


def _index_sql(db: Path, name: str) -> str | None:
    engine = sa.create_engine(f"sqlite:///{db}")
    try:
        with engine.connect() as conn:
            row = conn.execute(
                sa.text(
                    "SELECT sql FROM sqlite_master "
                    "WHERE type='index' AND name=:n"
                ),
                {"n": name},
            ).first()
            return row[0] if row else None
    finally:
        engine.dispose()


@pytest.mark.integration
def test_0009_adds_mikan_bangumi_url_column(tmp_path):
    db = tmp_path / "mig.db"
    env = os.environ.copy()
    env["AB_ALEMBIC_DB_URL"] = f"sqlite+aiosqlite:///{db}"
    result = _run_alembic("0009_add_mikan_bangumi_url", env)
    assert result.returncode == 0, result.stderr

    cols = _bangumi_columns(db)
    assert "mikan_bangumi_url" in cols


@pytest.mark.integration
def test_0009_creates_partial_unique_index(tmp_path):
    db = tmp_path / "mig.db"
    env = os.environ.copy()
    env["AB_ALEMBIC_DB_URL"] = f"sqlite+aiosqlite:///{db}"
    result = _run_alembic("0009_add_mikan_bangumi_url", env)
    assert result.returncode == 0, result.stderr

    sql = _index_sql(db, "uq_bangumi_mikan_url")
    assert sql is not None, "partial unique index missing"
    assert "UNIQUE" in sql.upper()
    assert "mikan_bangumi_url IS NOT NULL" in sql
    assert "deleted = 0" in sql


@pytest.mark.integration
def test_0009_index_enforces_uniqueness_across_rows(tmp_path):
    """Two live bangumi may not share the same canonical URL; the partial
    clause lets NULL values co-exist without triggering the constraint."""
    db = tmp_path / "mig.db"
    env = os.environ.copy()
    env["AB_ALEMBIC_DB_URL"] = f"sqlite+aiosqlite:///{db}"
    assert _run_alembic("0009_add_mikan_bangumi_url", env).returncode == 0

    engine = sa.create_engine(f"sqlite:///{db}")
    try:
        with engine.begin() as conn:
            # Need a series row for FK — insert a minimal placeholder.
            conn.execute(
                sa.text(
                    "INSERT INTO series (id, canonical_title, normalized_title, "
                    "season, default_offset, pending_review, root_path) "
                    "VALUES (1, 'T', 't', 1, 0, 0, '/x')"
                )
            )
            # Two bangumi with NULL url → fine
            conn.execute(sa.text(
                "INSERT INTO bangumi (id, series_id, group_name, eps_collect, "
                "\"offset\", filter, rss_link, added, deleted, pending_review, "
                "active) VALUES (1, 1, 'g', 0, 0, '', '', 0, 0, 0, 1)"
            ))
            conn.execute(sa.text(
                "INSERT INTO bangumi (id, series_id, group_name, eps_collect, "
                "\"offset\", filter, rss_link, added, deleted, pending_review, "
                "active) VALUES (2, 1, 'g', 0, 0, '', '', 0, 0, 0, 1)"
            ))
            # Stamp the same URL on the first → allowed.
            conn.execute(sa.text(
                "UPDATE bangumi SET mikan_bangumi_url = "
                "'https://mikanani.me/Home/Bangumi/3901#1243' WHERE id = 1"
            ))

        with pytest.raises(sa.exc.IntegrityError):
            with engine.begin() as conn:
                conn.execute(sa.text(
                    "UPDATE bangumi SET mikan_bangumi_url = "
                    "'https://mikanani.me/Home/Bangumi/3901#1243' WHERE id = 2"
                ))

        # Soft-deleting id=1 frees the URL for id=2.
        with engine.begin() as conn:
            conn.execute(sa.text("UPDATE bangumi SET deleted = 1 WHERE id = 1"))
            conn.execute(sa.text(
                "UPDATE bangumi SET mikan_bangumi_url = "
                "'https://mikanani.me/Home/Bangumi/3901#1243' WHERE id = 2"
            ))
    finally:
        engine.dispose()
