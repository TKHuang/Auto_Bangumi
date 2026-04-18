"""lockdown_bangumi_identity

Revision ID: 0008_lockdown_bangumi_identity
Revises: 0007_add_bangumi_series_link
Create Date: 2026-04-18

Stage C (destructive). Drops legacy bangumi columns now that
backfill_series.py + migrate_duplicates.py have produced a clean
series_id-driven identity. Adds the partial UNIQUE constraints that lock
identity in place.

PRECONDITIONS (caller must verify before running upgrade head past 0007):
  - Every undeleted bangumi has series_id NOT NULL
  - Duplicates have been merged (otherwise UNIQUE blows up at upgrade)
  - bangumi.db has been backed up

Downgrade restores the dropped columns as nullable but cannot restore
their data — restore from backup if you need the legacy values.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0008_lockdown_bangumi_identity"
down_revision: Union[str, Sequence[str], None] = "0007_add_bangumi_series_link"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("bangumi") as batch_op:
        # Drop legacy composite-key UNIQUE
        batch_op.drop_constraint(
            "uq_bangumi_title_season_group", type_="unique"
        )
        # Drop legacy columns
        batch_op.drop_column("save_path")
        batch_op.drop_column("official_title")
        batch_op.drop_column("year")
        batch_op.drop_column("season")
        batch_op.drop_column("season_raw")
        batch_op.drop_column("title_raw")
        batch_op.drop_column("poster_link")
        # Make series_id NOT NULL
        batch_op.alter_column(
            "series_id", existing_type=sa.Integer(), nullable=False
        )

    # Partial UNIQUEs (encoded via op.execute since SQLAlchemy autogenerate
    # can't round-trip them; mirrored on the ORM via Index(sqlite_where=...))
    op.execute(
        "CREATE UNIQUE INDEX uq_bangumi_series_subgroup "
        "ON bangumi (series_id, mikan_subgroup_id) WHERE deleted = 0"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_bangumi_series_rss_fallback "
        "ON bangumi (series_id, rss_id) "
        "WHERE mikan_subgroup_id IS NULL AND deleted = 0"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_bangumi_series_rss_fallback")
    op.execute("DROP INDEX IF EXISTS uq_bangumi_series_subgroup")

    with op.batch_alter_table("bangumi") as batch_op:
        batch_op.alter_column(
            "series_id", existing_type=sa.Integer(), nullable=True
        )
        batch_op.add_column(sa.Column("poster_link", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("title_raw", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("season_raw", sa.String(), nullable=True))
        batch_op.add_column(sa.Column(
            "season", sa.Integer(), nullable=True
        ))
        batch_op.add_column(sa.Column("year", sa.String(), nullable=True))
        batch_op.add_column(sa.Column(
            "official_title", sa.String(), nullable=True
        ))
        batch_op.add_column(sa.Column("save_path", sa.String(), nullable=True))
        batch_op.create_unique_constraint(
            "uq_bangumi_title_season_group",
            ["official_title", "season", "group_name"],
        )
