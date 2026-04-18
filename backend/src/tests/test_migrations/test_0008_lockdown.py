"""Tests for migration 0008: bangumi identity lockdown (destructive)."""
import os
import subprocess
from pathlib import Path

import pytest
import sqlalchemy as sa

BACKEND_DIR = Path(__file__).parent.parent.parent.parent


def _run_alembic(target: str, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["uv", "run", "alembic", "upgrade", target],
        cwd=BACKEND_DIR, env=env, capture_output=True, text=True,
    )


def _bangumi_columns(db: Path) -> set[str]:
    engine = sa.create_engine(f"sqlite:///{db}")
    inspector = sa.inspect(engine)
    return {c["name"] for c in inspector.get_columns("bangumi")}


@pytest.mark.integration
def test_0008_drops_legacy_bangumi_columns(tmp_path):
    db = tmp_path / "test.db"
    env = os.environ.copy()
    env["AB_ALEMBIC_DB_URL"] = f"sqlite+aiosqlite:///{db}"
    result = _run_alembic("0008_lockdown_bangumi_identity", env)
    assert result.returncode == 0, result.stderr

    cols = _bangumi_columns(db)
    for dropped in (
        "save_path", "official_title", "year", "season",
        "season_raw", "title_raw", "poster_link",
    ):
        assert dropped not in cols, f"{dropped} should be dropped by 0008"


@pytest.mark.integration
def test_0008_makes_series_id_not_null(tmp_path):
    db = tmp_path / "test.db"
    env = os.environ.copy()
    env["AB_ALEMBIC_DB_URL"] = f"sqlite+aiosqlite:///{db}"
    result = _run_alembic("0008_lockdown_bangumi_identity", env)
    assert result.returncode == 0, result.stderr

    engine = sa.create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        with pytest.raises(sa.exc.IntegrityError):
            conn.execute(sa.text(
                "INSERT INTO bangumi (rss_id, group_name, eps_collect, "
                "offset, filter, rss_link, added, deleted, pending_review, "
                "created_at, updated_at, version, active) "
                "VALUES (NULL, 'g', 0, 0, '720', '', 0, 0, 0, "
                "'2026-01-01', '2026-01-01', 1, 1)"
            ))


@pytest.mark.integration
def test_0008_partial_unique_blocks_dup_subgroup(tmp_path):
    db = tmp_path / "test.db"
    env = os.environ.copy()
    env["AB_ALEMBIC_DB_URL"] = f"sqlite+aiosqlite:///{db}"
    result = _run_alembic("0008_lockdown_bangumi_identity", env)
    assert result.returncode == 0, result.stderr

    engine = sa.create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        conn.execute(sa.text(
            "INSERT INTO series (mikan_bangumi_id, canonical_title, "
            "normalized_title, season, root_path, default_offset, "
            "pending_review, created_at, updated_at, version) "
            "VALUES (1, 'X', 'x', 1, '/p/X', 0, 0, "
            "'2026-01-01', '2026-01-01', 1)"
        ))
        conn.execute(sa.text(
            "INSERT INTO bangumi (rss_id, group_name, eps_collect, "
            "offset, filter, rss_link, added, deleted, pending_review, "
            "created_at, updated_at, version, series_id, mikan_subgroup_id, "
            "active) "
            "VALUES (NULL, 'g1', 0, 0, '720', '', 0, 0, 0, "
            "'2026-01-01', '2026-01-01', 1, 1, 7, 1)"
        ))

    with engine.begin() as conn:
        with pytest.raises(sa.exc.IntegrityError):
            conn.execute(sa.text(
                "INSERT INTO bangumi (rss_id, group_name, eps_collect, "
                "offset, filter, rss_link, added, deleted, pending_review, "
                "created_at, updated_at, version, series_id, "
                "mikan_subgroup_id, active) "
                "VALUES (NULL, 'g2', 0, 0, '720', '', 0, 0, 0, "
                "'2026-01-01', '2026-01-01', 1, 1, 7, 1)"
            ))


@pytest.mark.integration
def test_0008_partial_unique_skips_deleted_rows(tmp_path):
    """Soft-deleted rows must NOT occupy the unique slot."""
    db = tmp_path / "test.db"
    env = os.environ.copy()
    env["AB_ALEMBIC_DB_URL"] = f"sqlite+aiosqlite:///{db}"
    result = _run_alembic("0008_lockdown_bangumi_identity", env)
    assert result.returncode == 0, result.stderr

    engine = sa.create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        conn.execute(sa.text(
            "INSERT INTO series (mikan_bangumi_id, canonical_title, "
            "normalized_title, season, root_path, default_offset, "
            "pending_review, created_at, updated_at, version) "
            "VALUES (1, 'X', 'x', 1, '/p/X', 0, 0, "
            "'2026-01-01', '2026-01-01', 1)"
        ))
        # First row is deleted=1 — should NOT block the second insert
        conn.execute(sa.text(
            "INSERT INTO bangumi (rss_id, group_name, eps_collect, "
            "offset, filter, rss_link, added, deleted, pending_review, "
            "created_at, updated_at, version, series_id, mikan_subgroup_id, "
            "active) "
            "VALUES (NULL, 'g1', 0, 0, '720', '', 0, 1, 0, "
            "'2026-01-01', '2026-01-01', 1, 1, 7, 0)"
        ))
        conn.execute(sa.text(
            "INSERT INTO bangumi (rss_id, group_name, eps_collect, "
            "offset, filter, rss_link, added, deleted, pending_review, "
            "created_at, updated_at, version, series_id, mikan_subgroup_id, "
            "active) "
            "VALUES (NULL, 'g2', 0, 0, '720', '', 0, 0, 0, "
            "'2026-01-01', '2026-01-01', 1, 1, 7, 1)"
        ))


@pytest.mark.integration
def test_0008_fallback_unique_uses_rss_when_subgroup_null(tmp_path):
    db = tmp_path / "test.db"
    env = os.environ.copy()
    env["AB_ALEMBIC_DB_URL"] = f"sqlite+aiosqlite:///{db}"
    result = _run_alembic("0008_lockdown_bangumi_identity", env)
    assert result.returncode == 0, result.stderr

    engine = sa.create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        conn.execute(sa.text(
            "INSERT INTO series (mikan_bangumi_id, canonical_title, "
            "normalized_title, season, root_path, default_offset, "
            "pending_review, created_at, updated_at, version) "
            "VALUES (NULL, 'X', 'x', 1, '/p/X', 0, 0, "
            "'2026-01-01', '2026-01-01', 1)"
        ))
        conn.execute(sa.text(
            "INSERT INTO rssitem (name, url, parser, aggregate, enabled, "
            "created_at, updated_at, version) "
            "VALUES ('r1', 'u1', 'mikan', 0, 1, "
            "'2026-01-01', '2026-01-01', 1)"
        ))
        conn.execute(sa.text(
            "INSERT INTO bangumi (rss_id, group_name, eps_collect, "
            "offset, filter, rss_link, added, deleted, pending_review, "
            "created_at, updated_at, version, series_id, mikan_subgroup_id, "
            "active) "
            "VALUES (1, 'g1', 0, 0, '720', '', 0, 0, 0, "
            "'2026-01-01', '2026-01-01', 1, 1, NULL, 1)"
        ))
    with engine.begin() as conn:
        with pytest.raises(sa.exc.IntegrityError):
            conn.execute(sa.text(
                "INSERT INTO bangumi (rss_id, group_name, eps_collect, "
                "offset, filter, rss_link, added, deleted, pending_review, "
                "created_at, updated_at, version, series_id, "
                "mikan_subgroup_id, active) "
                "VALUES (1, 'g2', 0, 0, '720', '', 0, 0, 0, "
                "'2026-01-01', '2026-01-01', 1, 1, NULL, 1)"
            ))
