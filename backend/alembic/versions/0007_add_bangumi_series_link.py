"""add_bangumi_series_link

Revision ID: 0007_add_bangumi_series_link
Revises: 0006_series_fallback_partial
Create Date: 2026-04-18

Stage B (additive). Bangumi gains the new identity surface as nullable
columns so the live ORM keeps working through backfill. Torrent gains
mikan_bangumi_id / mikan_subgroup_id for downstream Series resolution.

NOT NULL on bangumi.series_id and the partial UNIQUE constraints arrive
in 0008_lockdown_bangumi_identity, after backfill + migrate_duplicates.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0007_add_bangumi_series_link"
down_revision: Union[str, Sequence[str], None] = "0006_series_fallback_partial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("bangumi") as batch_op:
        batch_op.add_column(
            sa.Column("series_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("mikan_subgroup_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("1"),
            )
        )
        batch_op.add_column(
            sa.Column("path_override", sa.String(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("observed_groups", sa.Text(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_bangumi_series",
            "series",
            ["series_id"],
            ["id"],
        )
        batch_op.create_index(
            "ix_bangumi_series_id", ["series_id"], unique=False
        )

    with op.batch_alter_table("torrent") as batch_op:
        batch_op.add_column(
            sa.Column("mikan_bangumi_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("mikan_subgroup_id", sa.Integer(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("torrent") as batch_op:
        batch_op.drop_column("mikan_subgroup_id")
        batch_op.drop_column("mikan_bangumi_id")

    with op.batch_alter_table("bangumi") as batch_op:
        batch_op.drop_index("ix_bangumi_series_id")
        batch_op.drop_constraint("fk_bangumi_series", type_="foreignkey")
        batch_op.drop_column("observed_groups")
        batch_op.drop_column("path_override")
        batch_op.drop_column("active")
        batch_op.drop_column("mikan_subgroup_id")
        batch_op.drop_column("series_id")
