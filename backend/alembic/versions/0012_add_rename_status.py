"""add_rename_status_and_conflict_target_to_torrent

Revision ID: 0012_add_rename_status
Revises: 0011_normalize_torrent_hash
Create Date: 2026-05-04

The renamer used to track only ``renamed_at`` (timestamp) and rely on
PikPak's ``torrents_rename_file`` returning ``True`` even when PikPak rejected
the rename with "name already exists". That made the DB believe the file was
renamed when it really wasn't — the user lost an episode silently because the
media-library scraper couldn't match the raw filename.

This migration introduces:

* ``rename_status``         — explicit outcome for the latest rename attempt
                              (``pending`` / ``done`` / ``conflict`` / ``error``).
                              Defaults to ``pending`` for every existing row;
                              rows that already have ``renamed_at`` set are
                              backfilled to ``done`` so the renamer doesn't
                              try to redo them.
* ``rename_conflict_target`` — when a rename hits a name collision, the
                              renamer stores the contested target filename
                              here so the UI can show the user exactly which
                              file is blocked and why.

Both columns are nullable / have defaults so the change is backward-compatible
with older code that doesn't populate them.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0012_add_rename_status"
down_revision: Union[str, Sequence[str], None] = "0011_normalize_torrent_hash"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_RENAME_STATUS_ENUM = sa.Enum(
    "pending",
    "done",
    "conflict",
    "error",
    name="rename_status_enum",
)


def upgrade() -> None:
    with op.batch_alter_table("torrent", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "rename_status",
                _RENAME_STATUS_ENUM,
                nullable=False,
                server_default="pending",
            )
        )
        batch_op.add_column(
            sa.Column(
                "rename_conflict_target",
                sa.String(),
                nullable=True,
            )
        )

    # Existing already-renamed rows should land in DONE so the cron tick
    # doesn't pick them up again on next start.
    op.execute(
        "UPDATE torrent SET rename_status = 'done' "
        "WHERE renamed_at IS NOT NULL"
    )


def downgrade() -> None:
    with op.batch_alter_table("torrent", schema=None) as batch_op:
        batch_op.drop_column("rename_conflict_target")
        batch_op.drop_column("rename_status")
