"""Tests for migration 0007: additive bangumi + torrent columns."""
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


def _columns(db: Path, table: str) -> set[str]:
    engine = sa.create_engine(f"sqlite:///{db}")
    inspector = sa.inspect(engine)
    return {c["name"] for c in inspector.get_columns(table)}


@pytest.mark.integration
def test_0007_adds_bangumi_columns(tmp_path):
    db = tmp_path / "test.db"
    env = os.environ.copy()
    env["AB_ALEMBIC_DB_URL"] = f"sqlite+aiosqlite:///{db}"

    result = _run_alembic("0007_add_bangumi_series_link", env)
    assert result.returncode == 0, result.stderr

    cols = _columns(db, "bangumi")
    assert "series_id" in cols
    assert "mikan_subgroup_id" in cols
    assert "active" in cols
    assert "path_override" in cols
    assert "observed_groups" in cols
    # Old columns must remain — destructive drop happens in 0008
    assert "official_title" in cols
    assert "save_path" in cols


@pytest.mark.integration
def test_0007_adds_torrent_columns(tmp_path):
    db = tmp_path / "test.db"
    env = os.environ.copy()
    env["AB_ALEMBIC_DB_URL"] = f"sqlite+aiosqlite:///{db}"
    assert _run_alembic("0007_add_bangumi_series_link", env).returncode == 0

    cols = _columns(db, "torrent")
    assert "mikan_bangumi_id" in cols
    assert "mikan_subgroup_id" in cols


@pytest.mark.integration
def test_0007_active_default_true_for_existing_rows(tmp_path):
    """Server-default for active must be true so existing bangumi remain
    visible to the rename pipeline after migration."""
    db = tmp_path / "test.db"
    env = os.environ.copy()
    env["AB_ALEMBIC_DB_URL"] = f"sqlite+aiosqlite:///{db}"

    # Stop at 0006 (now the prior head before 0007) so we can seed a legacy
    # bangumi row, then upgrade to 0007.
    assert _run_alembic("0006_series_fallback_partial", env).returncode == 0

    engine = sa.create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        conn.execute(sa.text(
            "INSERT INTO bangumi (rss_id, official_title, title_raw, season, "
            "group_name, eps_collect, offset, filter, rss_link, added, "
            "deleted, pending_review, created_at, updated_at, version) "
            "VALUES (NULL, 'X', 'X', 1, 'G', 0, 0, '720', '', 0, 0, 0, "
            "'2026-01-01', '2026-01-01', 1)"
        ))

    assert _run_alembic("0007_add_bangumi_series_link", env).returncode == 0

    engine = sa.create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        active_val = conn.execute(
            sa.text("SELECT active FROM bangumi WHERE official_title='X'")
        ).scalar_one()
    assert active_val == 1


@pytest.mark.integration
def test_0007_downgrade_is_clean(tmp_path):
    db = tmp_path / "test.db"
    env = os.environ.copy()
    env["AB_ALEMBIC_DB_URL"] = f"sqlite+aiosqlite:///{db}"
    assert _run_alembic("0007_add_bangumi_series_link", env).returncode == 0

    result = subprocess.run(
        ["uv", "run", "alembic", "downgrade", "0006_series_fallback_partial"],
        cwd=BACKEND_DIR, env=env, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    cols = _columns(db, "bangumi")
    assert "series_id" not in cols
    assert "active" not in cols
