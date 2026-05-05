"""Tests for migration 0011: normalize torrent hashes safely."""
import os
import subprocess
from pathlib import Path

import pytest
import sqlalchemy as sa

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent.parent


def _run_alembic(target: str, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            "uv",
            "run",
            "alembic",
            "-c",
            str(BACKEND_DIR / "alembic.ini"),
            "upgrade",
            target,
        ],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )


def _seed_identity(conn: sa.Connection) -> None:
    conn.execute(sa.text(
        "INSERT INTO series (id, canonical_title, normalized_title, "
        "season, default_offset, pending_review, root_path) "
        "VALUES (1, 'T', 't', 1, 0, 0, '/x')"
    ))
    conn.execute(sa.text(
        "INSERT INTO bangumi (id, series_id, group_name, eps_collect, "
        "\"offset\", filter, rss_link, added, deleted, pending_review, active) "
        "VALUES (1, 1, 'g', 0, 0, '', '', 0, 0, 0, 1)"
    ))


@pytest.mark.integration
def test_0011_merges_casefold_duplicates_before_lowering(tmp_path):
    db = tmp_path / "mig.db"
    env = os.environ.copy()
    env["AB_ALEMBIC_DB_URL"] = f"sqlite+aiosqlite:///{db}"
    assert _run_alembic("0010_merge_history_set_null", env).returncode == 0

    engine = sa.create_engine(f"sqlite:///{db}")
    try:
        with engine.begin() as conn:
            _seed_identity(conn)
            conn.execute(sa.text(
                "INSERT INTO torrent "
                "(id, bangumi_id, name, url, hash, downloaded, state) "
                "VALUES (1, 1, 'raw', 'u1', 'ABCDEF', 0, 'pending')"
            ))
            conn.execute(sa.text(
                "INSERT INTO torrent "
                "(id, bangumi_id, name, url, hash, downloaded, state, pikpak_cloud_path) "
                "VALUES (2, 1, 'downloaded', 'u2', ' abcdef ', 1, 'completed', '/cloud')"
            ))
            conn.execute(sa.text(
                "INSERT INTO torrent "
                "(id, bangumi_id, name, url, hash, downloaded, state) "
                "VALUES (3, NULL, 'pending-a', 'u3', 'XYZ123', 0, 'pending')"
            ))
            conn.execute(sa.text(
                "INSERT INTO torrent "
                "(id, bangumi_id, name, url, hash, downloaded, state) "
                "VALUES (4, NULL, 'pending-b', 'u4', ' xyz123 ', 0, 'pending')"
            ))
    finally:
        engine.dispose()

    result = _run_alembic("0011_normalize_torrent_hash", env)
    assert result.returncode == 0, result.stderr

    engine = sa.create_engine(f"sqlite:///{db}")
    try:
        with engine.connect() as conn:
            bound = conn.execute(sa.text(
                "SELECT hash, downloaded, pikpak_cloud_path FROM torrent "
                "WHERE bangumi_id = 1"
            )).all()
            assert bound == [("abcdef", 1, "/cloud")]

            unbound = conn.execute(sa.text(
                "SELECT hash, count(*) FROM torrent "
                "WHERE bangumi_id IS NULL GROUP BY hash"
            )).all()
            assert unbound == [("xyz123", 1)]

        with pytest.raises(sa.exc.IntegrityError):
            with engine.begin() as conn:
                conn.execute(sa.text(
                    "INSERT INTO torrent "
                    "(bangumi_id, name, url, hash, downloaded, state) "
                    "VALUES (NULL, 'dup', 'u5', 'xyz123', 0, 'pending')"
                ))
    finally:
        engine.dispose()
