"""Alembic configuration and baseline correctness tests."""
import os
import subprocess
import sys
from pathlib import Path

import pytest
import sqlalchemy as sa

BACKEND_DIR = Path(__file__).parent.parent.parent.parent  # backend/


@pytest.mark.unit
def test_alembic_env_resolves_config():
    """`alembic current` must succeed, proving env.py can load target_metadata."""
    result = subprocess.run(
        ["uv", "run", "alembic", "current"],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"alembic current failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    )


@pytest.mark.unit
def test_alembic_env_loads_target_metadata():
    """env.py must import Base.metadata so autogenerate works."""
    env_py = (BACKEND_DIR / "alembic" / "env.py").read_text()
    assert "from module.domain.models.base import Base" in env_py, (
        "env.py must import Base from module.domain.models.base"
    )
    assert "target_metadata = Base.metadata" in env_py, (
        "env.py must assign target_metadata = Base.metadata"
    )
    # All four model modules must be imported so their tables register with metadata
    for module in ("user", "rss", "bangumi", "torrent"):
        assert f"import module.domain.models.{module}" in env_py or \
               f"from module.domain.models import {module}" in env_py or \
               f"from module.domain.models.{module}" in env_py, (
            f"env.py must import module.domain.models.{module} to register tables"
        )


@pytest.mark.unit
def test_baseline_migration_exists():
    """A single baseline migration must exist under versions/."""
    versions_dir = BACKEND_DIR / "alembic" / "versions"
    migrations = [f for f in versions_dir.glob("*.py") if not f.name.startswith("__")]
    assert len(migrations) >= 1, "Expected at least one migration file"
    assert any("baseline" in m.name.lower() for m in migrations), (
        "Expected a baseline migration file (name containing 'baseline')"
    )


@pytest.mark.integration
def test_baseline_upgrade_on_empty_db_matches_metadata(tmp_path):
    """
    After `alembic upgrade head` on empty DB, all Base.metadata tables exist
    with matching columns.
    """
    fresh_db = tmp_path / "fresh.db"
    env = os.environ.copy()
    env["AB_ALEMBIC_DB_URL"] = f"sqlite+aiosqlite:///{fresh_db}"

    result = subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"alembic upgrade head failed:\n{result.stderr}"
    )

    engine = sa.create_engine(f"sqlite:///{fresh_db}")
    inspector = sa.inspect(engine)
    db_tables = set(inspector.get_table_names()) - {"alembic_version", "sqlite_sequence"}

    sys.path.insert(0, str(BACKEND_DIR / "src"))
    from module.domain.models.base import Base
    import module.domain.models.user  # noqa: F401
    import module.domain.models.rss  # noqa: F401
    import module.domain.models.bangumi  # noqa: F401
    import module.domain.models.torrent  # noqa: F401
    import module.domain.models.series  # noqa: F401

    model_tables = set(Base.metadata.tables.keys())
    assert db_tables == model_tables, (
        f"Table parity mismatch.\nOnly in DB: {db_tables - model_tables}\n"
        f"Only in model: {model_tables - db_tables}"
    )
