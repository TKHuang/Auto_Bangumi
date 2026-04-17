"""Alembic configuration and baseline correctness tests."""
import subprocess
from pathlib import Path

import pytest

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
