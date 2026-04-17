"""Verify the full Phase 1 migration chain applies and reverts cleanly."""
import os
import subprocess
from pathlib import Path

import pytest
import sqlalchemy as sa

BACKEND_DIR = Path(__file__).parent.parent.parent.parent


def _run_alembic(args: list[str], db_path: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["AB_ALEMBIC_DB_URL"] = f"sqlite+aiosqlite:///{db_path}"
    return subprocess.run(
        ["uv", "run", "alembic", *args],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )


@pytest.mark.integration
def test_full_upgrade_creates_all_new_tables(tmp_path):
    db = tmp_path / "fresh.db"

    result = _run_alembic(["upgrade", "head"], db)
    assert result.returncode == 0, result.stderr

    engine = sa.create_engine(f"sqlite:///{db}")
    tables = set(sa.inspect(engine).get_table_names())
    assert {"bangumi", "rssitem", "torrent", "user"}.issubset(tables)
    assert {
        "series",
        "mikan_episode_ref",
        "pending_torrent_enrichment",
        "bangumi_merge_history",
    }.issubset(tables)


@pytest.mark.integration
def test_downgrade_to_baseline_drops_new_tables(tmp_path):
    db = tmp_path / "roll.db"

    assert _run_alembic(["upgrade", "head"], db).returncode == 0
    assert _run_alembic(["downgrade", "0001_baseline"], db).returncode == 0

    engine = sa.create_engine(f"sqlite:///{db}")
    tables = set(sa.inspect(engine).get_table_names())
    assert "series" not in tables
    assert "mikan_episode_ref" not in tables
    assert "pending_torrent_enrichment" not in tables
    assert "bangumi_merge_history" not in tables
    assert {"bangumi", "rssitem", "torrent", "user"}.issubset(tables)


@pytest.mark.integration
def test_upgrade_downgrade_upgrade_is_idempotent(tmp_path):
    db = tmp_path / "cycle.db"

    assert _run_alembic(["upgrade", "head"], db).returncode == 0
    assert _run_alembic(["downgrade", "base"], db).returncode == 0
    assert _run_alembic(["upgrade", "head"], db).returncode == 0

    engine = sa.create_engine(f"sqlite:///{db}")
    tables = set(sa.inspect(engine).get_table_names())
    assert {
        "bangumi", "rssitem", "torrent", "user",
        "series", "mikan_episode_ref",
        "pending_torrent_enrichment", "bangumi_merge_history",
    }.issubset(tables)
