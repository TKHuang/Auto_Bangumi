"""Compare Base.metadata to the production DB schema.

Run against a copy of production bangumi.db to verify that the ORM models
(Base.metadata) include every column present in a real migrated database.
This catches cases where _run_migrations added a column but the model wasn't
updated.

Usage:
    uv run python scripts/audit_schema_parity.py /path/to/bangumi.db
"""
import sys
from pathlib import Path

BACKEND_SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(BACKEND_SRC))

import sqlalchemy as sa

from module.domain.models.base import Base
import module.domain.models.user  # noqa: F401
import module.domain.models.rss  # noqa: F401
import module.domain.models.bangumi  # noqa: F401
import module.domain.models.torrent  # noqa: F401


def audit(db_path: str) -> int:
    """Return 0 if parity, non-zero if drift detected."""
    url = f"sqlite:///{db_path}"
    engine = sa.create_engine(url)
    inspector = sa.inspect(engine)

    model_tables = set(Base.metadata.tables.keys())
    db_tables = set(inspector.get_table_names())

    print(f"Model tables: {sorted(model_tables)}")
    print(f"DB tables:    {sorted(db_tables)}")

    only_in_db = db_tables - model_tables - {"sqlite_sequence", "alembic_version"}
    if only_in_db:
        print(f"Tables only in DB: {sorted(only_in_db)}")

    drift_found = bool(only_in_db)

    for tname in sorted(model_tables & db_tables):
        model_cols = {c.name for c in Base.metadata.tables[tname].columns}
        db_cols = {c["name"] for c in inspector.get_columns(tname)}
        only_in_db_c = db_cols - model_cols
        only_in_model_c = model_cols - db_cols
        if only_in_db_c or only_in_model_c:
            print(f"\nTable {tname}:")
            if only_in_db_c:
                print(f"  Only in DB: {sorted(only_in_db_c)}")
                drift_found = True
            if only_in_model_c:
                print(f"  Only in model: {sorted(only_in_model_c)}")

    if drift_found:
        print("\n=== DRIFT DETECTED ===")
        return 1
    print("\n=== PARITY OK ===")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: audit_schema_parity.py <path_to_bangumi.db>")
        sys.exit(2)
    sys.exit(audit(sys.argv[1]))
