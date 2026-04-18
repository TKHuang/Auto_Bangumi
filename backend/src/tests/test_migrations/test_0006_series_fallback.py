"""Tests for migration 0006: convert series fallback constraints to partial."""
import os
import subprocess
from pathlib import Path

import pytest
import sqlalchemy as sa

BACKEND_DIR = Path(__file__).parent.parent.parent.parent  # backend/


def _run_alembic(target: str, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["uv", "run", "alembic", "upgrade", target],
        cwd=BACKEND_DIR, env=env, capture_output=True, text=True,
    )


@pytest.mark.integration
def test_0006_allows_mikan_series_to_share_fallback_key(tmp_path):
    """After 0006, two Mikan-sourced series may share (normalized_title, season,
    cour_part) because the fallback partial index excludes them."""
    db = tmp_path / "test.db"
    env = os.environ.copy()
    env["AB_ALEMBIC_DB_URL"] = f"sqlite+aiosqlite:///{db}"

    result = _run_alembic("0006_series_fallback_partial", env)
    assert result.returncode == 0, f"upgrade failed:\n{result.stderr}"

    engine = sa.create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        conn.execute(sa.text(
            "INSERT INTO series (mikan_bangumi_id, canonical_title, "
            "normalized_title, season, cour_part, root_path, default_offset, "
            "pending_review, created_at, updated_at, version) "
            "VALUES (1001, 'A', 'foo', 1, NULL, '/p/A', 0, 0, "
            "'2026-01-01', '2026-01-01', 1)"
        ))
        # Same fallback key, different Mikan id → should NOT collide
        conn.execute(sa.text(
            "INSERT INTO series (mikan_bangumi_id, canonical_title, "
            "normalized_title, season, cour_part, root_path, default_offset, "
            "pending_review, created_at, updated_at, version) "
            "VALUES (1002, 'B', 'foo', 1, NULL, '/p/B', 0, 0, "
            "'2026-01-01', '2026-01-01', 1)"
        ))


@pytest.mark.integration
def test_0006_still_blocks_duplicate_non_mikan_fallback(tmp_path):
    """Two non-Mikan series with identical fallback key must still collide."""
    db = tmp_path / "test.db"
    env = os.environ.copy()
    env["AB_ALEMBIC_DB_URL"] = f"sqlite+aiosqlite:///{db}"
    assert _run_alembic("0006_series_fallback_partial", env).returncode == 0

    engine = sa.create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        conn.execute(sa.text(
            "INSERT INTO series (mikan_bangumi_id, canonical_title, "
            "normalized_title, season, cour_part, root_path, default_offset, "
            "pending_review, created_at, updated_at, version) "
            "VALUES (NULL, 'A', 'foo', 1, NULL, '/p/A', 0, 0, "
            "'2026-01-01', '2026-01-01', 1)"
        ))
    with engine.begin() as conn:
        with pytest.raises(sa.exc.IntegrityError):
            conn.execute(sa.text(
                "INSERT INTO series (mikan_bangumi_id, canonical_title, "
                "normalized_title, season, cour_part, root_path, default_offset, "
                "pending_review, created_at, updated_at, version) "
                "VALUES (NULL, 'B', 'foo', 1, NULL, '/p/B', 0, 0, "
                "'2026-01-01', '2026-01-01', 1)"
            ))


@pytest.mark.integration
def test_0006_mikan_unique_still_enforced(tmp_path):
    """uq_series_mikan must continue to block duplicate mikan_bangumi_id."""
    db = tmp_path / "test.db"
    env = os.environ.copy()
    env["AB_ALEMBIC_DB_URL"] = f"sqlite+aiosqlite:///{db}"
    assert _run_alembic("0006_series_fallback_partial", env).returncode == 0

    engine = sa.create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        conn.execute(sa.text(
            "INSERT INTO series (mikan_bangumi_id, canonical_title, "
            "normalized_title, season, cour_part, root_path, default_offset, "
            "pending_review, created_at, updated_at, version) "
            "VALUES (2001, 'A', 'a', 1, NULL, '/p/A', 0, 0, "
            "'2026-01-01', '2026-01-01', 1)"
        ))
    with engine.begin() as conn:
        with pytest.raises(sa.exc.IntegrityError):
            conn.execute(sa.text(
                "INSERT INTO series (mikan_bangumi_id, canonical_title, "
                "normalized_title, season, cour_part, root_path, default_offset, "
                "pending_review, created_at, updated_at, version) "
                "VALUES (2001, 'B', 'b', 1, NULL, '/p/B', 0, 0, "
                "'2026-01-01', '2026-01-01', 1)"
            ))


@pytest.mark.integration
def test_0006_null_cour_helper_allows_mikan_rows_to_share(tmp_path):
    """uq_series_fallback_null_cour has WHERE mikan_bangumi_id IS NULL, so two
    Mikan rows with identical (normalized_title, season, cour_part=NULL) must
    both insert successfully — they are outside the index predicate."""
    db = tmp_path / "test.db"
    env = os.environ.copy()
    env["AB_ALEMBIC_DB_URL"] = f"sqlite+aiosqlite:///{db}"
    assert _run_alembic("0006_series_fallback_partial", env).returncode == 0

    engine = sa.create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        conn.execute(sa.text(
            "INSERT INTO series (mikan_bangumi_id, canonical_title, "
            "normalized_title, season, cour_part, root_path, default_offset, "
            "pending_review, created_at, updated_at, version) "
            "VALUES (3001, 'A', 'ncfoo', 1, NULL, '/p/A', 0, 0, "
            "'2026-01-01', '2026-01-01', 1)"
        ))
        # Same (normalized_title, season, cour_part=NULL), different mikan id
        # → falls outside uq_series_fallback_null_cour predicate, must succeed
        conn.execute(sa.text(
            "INSERT INTO series (mikan_bangumi_id, canonical_title, "
            "normalized_title, season, cour_part, root_path, default_offset, "
            "pending_review, created_at, updated_at, version) "
            "VALUES (3002, 'B', 'ncfoo', 1, NULL, '/p/B', 0, 0, "
            "'2026-01-01', '2026-01-01', 1)"
        ))


@pytest.mark.integration
def test_0006_null_cour_helper_blocks_dup_non_mikan(tmp_path):
    """uq_series_fallback_null_cour must block a second non-Mikan row that
    shares (normalized_title, season) when cour_part IS NULL — the predicate
    WHERE mikan_bangumi_id IS NULL AND cour_part IS NULL applies to both rows."""
    db = tmp_path / "test.db"
    env = os.environ.copy()
    env["AB_ALEMBIC_DB_URL"] = f"sqlite+aiosqlite:///{db}"
    assert _run_alembic("0006_series_fallback_partial", env).returncode == 0

    engine = sa.create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        conn.execute(sa.text(
            "INSERT INTO series (mikan_bangumi_id, canonical_title, "
            "normalized_title, season, cour_part, root_path, default_offset, "
            "pending_review, created_at, updated_at, version) "
            "VALUES (NULL, 'A', 'nfoo', 1, NULL, '/p/A', 0, 0, "
            "'2026-01-01', '2026-01-01', 1)"
        ))
    with engine.begin() as conn:
        # Same (normalized_title, season, cour_part=NULL, mikan_bangumi_id=NULL)
        # → inside the partial index predicate, must be rejected
        with pytest.raises(sa.exc.IntegrityError):
            conn.execute(sa.text(
                "INSERT INTO series (mikan_bangumi_id, canonical_title, "
                "normalized_title, season, cour_part, root_path, default_offset, "
                "pending_review, created_at, updated_at, version) "
                "VALUES (NULL, 'B', 'nfoo', 1, NULL, '/p/B', 0, 0, "
                "'2026-01-01', '2026-01-01', 1)"
            ))
