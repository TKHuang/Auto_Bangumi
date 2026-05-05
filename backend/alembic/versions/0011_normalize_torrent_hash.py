"""normalize_torrent_hash_lower_and_partial_uniques

Revision ID: 0011_normalize_torrent_hash
Revises: 0010_merge_history_set_null
Create Date: 2026-05-04

Two related fixes shipped together because both touch ``torrent.hash``:

1. **Backfill** every ``torrent.hash`` to lowercase. New writes are
   normalized at the model level via ``@validates("hash")``, but legacy
   rows from before that change can still hold uppercase values written
   by Mikan exports / direct API pastes.

2. **Partial unique index** ``uq_torrent_hash_unbound`` for the
   ``hash IS NOT NULL AND bangumi_id IS NULL`` slice. The composite
   ``UNIQUE (hash, bangumi_id)`` constraint added in 0001 silently allows
   duplicate rows when ``bangumi_id`` is NULL because SQLite treats every
   NULL as distinct in unique constraints. Without the partial index a
   pending-enrichment row keeps re-inserting on each scheduler tick.

Both are forward-compatible: rerunning the migration is a no-op because the
``UPDATE`` is idempotent and ``CREATE UNIQUE INDEX IF NOT EXISTS`` short
circuits when present.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0011_normalize_torrent_hash"
down_revision: Union[str, Sequence[str], None] = "0010_merge_history_set_null"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TORRENT_COLUMNS = (
    "id",
    "bangumi_id",
    "rss_id",
    "name",
    "url",
    "homepage",
    "hash",
    "state",
    "downloaded",
    "renamed_at",
    "renamed_file_count",
    "pikpak_cloud_path",
    "pikpak_task_id",
    "mikan_bangumi_id",
    "mikan_subgroup_id",
)


def _norm_hash(raw: str) -> str:
    return raw.strip().lower()


def _has_value(value) -> bool:
    return value is not None and value != ""


def _row_score(row: dict) -> tuple:
    return (
        1 if row.get("state") == "excluded" else 0,
        1 if row.get("downloaded") else 0,
        1 if row.get("renamed_at") else 0,
        1 if row.get("pikpak_cloud_path") else 0,
        1 if row.get("pikpak_task_id") else 0,
        1 if row.get("url") else 0,
        1 if row.get("name") else 0,
        -(row.get("id") or 0),
    )


def _pick(rows: list[dict], column: str):
    for row in sorted(rows, key=_row_score, reverse=True):
        value = row.get(column)
        if _has_value(value):
            return value
    return None


def _merge_hash_collisions() -> None:
    """Collapse rows that will collide after ``LOWER(TRIM(hash))``."""
    conn = op.get_bind()
    rows = [
        dict(row)
        for row in conn.execute(sa.text(
            "SELECT " + ", ".join(_TORRENT_COLUMNS) + " "
            "FROM torrent WHERE hash IS NOT NULL"
        )).mappings()
    ]

    groups: dict[tuple[str, int | None], list[dict]] = {}
    for row in rows:
        groups.setdefault(
            (_norm_hash(row["hash"]), row["bangumi_id"]),
            [],
        ).append(row)

    for (norm_hash, _bangumi_id), group in groups.items():
        if len(group) == 1:
            continue

        ordered = sorted(group, key=_row_score, reverse=True)
        keeper = ordered[0]
        duplicate_ids = [row["id"] for row in ordered[1:]]
        state = "excluded" if any(row.get("state") == "excluded" for row in group) else (
            _pick(group, "state") or "pending"
        )
        renamed_counts = [
            row["renamed_file_count"]
            for row in group
            if row.get("renamed_file_count") is not None
        ]
        values = {
            "id": keeper["id"],
            "hash": norm_hash,
            "rss_id": _pick(group, "rss_id"),
            "name": _pick(group, "name") or "",
            "url": _pick(group, "url") or "",
            "homepage": _pick(group, "homepage"),
            "state": state,
            "downloaded": 1
            if state == "excluded" or any(row.get("downloaded") for row in group)
            else 0,
            "renamed_at": _pick(group, "renamed_at"),
            "renamed_file_count": max(renamed_counts) if renamed_counts else None,
            "pikpak_cloud_path": _pick(group, "pikpak_cloud_path"),
            "pikpak_task_id": _pick(group, "pikpak_task_id"),
            "mikan_bangumi_id": _pick(group, "mikan_bangumi_id"),
            "mikan_subgroup_id": _pick(group, "mikan_subgroup_id"),
        }

        for duplicate_id in duplicate_ids:
            conn.execute(
                sa.text("DELETE FROM torrent WHERE id = :id"),
                {"id": duplicate_id},
            )

        conn.execute(sa.text(
            "UPDATE torrent SET "
            "hash = :hash, rss_id = :rss_id, name = :name, url = :url, "
            "homepage = :homepage, state = :state, downloaded = :downloaded, "
            "renamed_at = :renamed_at, renamed_file_count = :renamed_file_count, "
            "pikpak_cloud_path = :pikpak_cloud_path, "
            "pikpak_task_id = :pikpak_task_id, "
            "mikan_bangumi_id = :mikan_bangumi_id, "
            "mikan_subgroup_id = :mikan_subgroup_id "
            "WHERE id = :id"
        ), values)


def upgrade() -> None:
    _merge_hash_collisions()

    # 1. Backfill — strip + lowercase every existing hash.
    op.execute(
        "UPDATE torrent "
        "SET hash = LOWER(TRIM(hash)) "
        "WHERE hash IS NOT NULL AND hash <> LOWER(TRIM(hash))"
    )

    # 2. Partial unique covering rows whose hash is set but bangumi_id is
    #    NULL (pending-enrichment sentinel rows). The pre-existing
    #    UNIQUE(hash, bangumi_id) does NOT cover this case in SQLite.
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_torrent_hash_unbound "
        "ON torrent (hash) "
        "WHERE hash IS NOT NULL AND bangumi_id IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_torrent_hash_unbound")
    # No way to "un-lowercase" the backfill — leave data as-is on downgrade.
