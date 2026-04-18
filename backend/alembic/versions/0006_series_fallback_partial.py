"""series_fallback_partial

Revision ID: 0006_series_fallback_partial
Revises: 0005_add_merge_history
Create Date: 2026-04-18

Convert uq_series_fallback (and uq_series_fallback_null_cour) into partial
indexes scoped to WHERE mikan_bangumi_id IS NULL. Mikan-sourced series are
already identified by uq_series_mikan; the fallback key is only meaningful
for non-Mikan rows. This unblocks the proper Tier-3 cross-source create
path in IdentityResolver.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0006_series_fallback_partial"
down_revision: Union[str, Sequence[str], None] = "0005_add_merge_history"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the existing full UNIQUE constraint and the NULL-cour helper,
    # then recreate both as partial indexes scoped to non-Mikan rows.
    with op.batch_alter_table("series") as batch_op:
        batch_op.drop_constraint("uq_series_fallback", type_="unique")
    op.execute("DROP INDEX IF EXISTS uq_series_fallback_null_cour")

    op.execute(
        "CREATE UNIQUE INDEX uq_series_fallback "
        "ON series (normalized_title, season, cour_part) "
        "WHERE mikan_bangumi_id IS NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_series_fallback_null_cour "
        "ON series (normalized_title, season) "
        "WHERE mikan_bangumi_id IS NULL AND cour_part IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_series_fallback")
    op.execute("DROP INDEX IF EXISTS uq_series_fallback_null_cour")

    # Restore the original (full) constraint + helper from 0002.
    with op.batch_alter_table("series") as batch_op:
        batch_op.create_unique_constraint(
            "uq_series_fallback",
            ["normalized_title", "season", "cour_part"],
        )
    op.execute(
        "CREATE UNIQUE INDEX uq_series_fallback_null_cour "
        "ON series (normalized_title, season) WHERE cour_part IS NULL"
    )
