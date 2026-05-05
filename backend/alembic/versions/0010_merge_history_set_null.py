"""make_merge_history_fk_nullable_set_null

Revision ID: 0010_merge_history_set_null
Revises: 0009_add_mikan_bangumi_url
Create Date: 2026-05-04

Purpose
-------
Migration 0005 added ``bangumi_merge_history`` with two FKs back to
``bangumi`` (winner / loser).  Both columns were declared NOT NULL with no
``ondelete`` policy, which means ``DELETE FROM bangumi WHERE id = ?`` raises
``IntegrityError`` whenever the bangumi has ever appeared in a merge — even
if the merge has been undone.

Audit rows must outlive the underlying bangumi (they're the only proof the
merge happened), so we recreate the columns as nullable with
``ON DELETE SET NULL``.  Existing rows keep their winner / loser ids;
SQLite's ``batch_alter_table`` handles the table rebuild atomically.

Idempotent guards: ``op.batch_alter_table`` is a no-op rebuild when the
target shape already matches, so re-running this migration on an already
upgraded database is safe.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0010_merge_history_set_null"
down_revision: Union[str, Sequence[str], None] = "0009_add_mikan_bangumi_url"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("bangumi_merge_history", schema=None) as batch_op:
        # Drop FKs by their migration-0005 names so we can recreate them with
        # the new ondelete clause.
        batch_op.drop_constraint(
            "fk_bangumi_merge_history_winner_bangumi_id_bangumi",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_bangumi_merge_history_loser_bangumi_id_bangumi",
            type_="foreignkey",
        )

        batch_op.alter_column(
            "winner_bangumi_id",
            existing_type=sa.Integer(),
            nullable=True,
        )
        batch_op.alter_column(
            "loser_bangumi_id",
            existing_type=sa.Integer(),
            nullable=True,
        )

        batch_op.create_foreign_key(
            "fk_bangumi_merge_history_winner_bangumi_id_bangumi",
            "bangumi",
            ["winner_bangumi_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_bangumi_merge_history_loser_bangumi_id_bangumi",
            "bangumi",
            ["loser_bangumi_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("bangumi_merge_history", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_bangumi_merge_history_winner_bangumi_id_bangumi",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_bangumi_merge_history_loser_bangumi_id_bangumi",
            type_="foreignkey",
        )

        batch_op.alter_column(
            "winner_bangumi_id",
            existing_type=sa.Integer(),
            nullable=False,
        )
        batch_op.alter_column(
            "loser_bangumi_id",
            existing_type=sa.Integer(),
            nullable=False,
        )

        batch_op.create_foreign_key(
            "fk_bangumi_merge_history_winner_bangumi_id_bangumi",
            "bangumi",
            ["winner_bangumi_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_bangumi_merge_history_loser_bangumi_id_bangumi",
            "bangumi",
            ["loser_bangumi_id"],
            ["id"],
        )
