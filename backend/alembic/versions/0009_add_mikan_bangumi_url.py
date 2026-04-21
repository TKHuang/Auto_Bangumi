"""add_mikan_bangumi_url

Revision ID: 0009_add_mikan_bangumi_url
Revises: 0008_lockdown_bangumi_identity
Create Date: 2026-04-20

Adds bangumi.mikan_bangumi_url — the canonical Mikan bangumi-page URL (e.g.
``https://mikanani.me/Home/Bangumi/3901#1243``) that pairs a series with a
specific subgroup. Stored in the human-facing fragment form on purpose so
operators can click straight through from the WebUI to verify identity.

Doubles as the short-circuit key for aggregate RSS ingestion: once a human
resolves a bangumi in the pending queue, future episodes whose Mikan page
maps to the same URL bind automatically — no per-fansub parser required.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0009_add_mikan_bangumi_url"
down_revision: Union[str, Sequence[str], None] = "0008_lockdown_bangumi_identity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("bangumi") as batch_op:
        batch_op.add_column(
            sa.Column("mikan_bangumi_url", sa.String(), nullable=True)
        )

    # Partial unique so distinct bangumi rows never share the same Mikan page
    # identity, but NULL values (pre-resolve legacy rows) remain unconstrained.
    op.execute(
        "CREATE UNIQUE INDEX uq_bangumi_mikan_url "
        "ON bangumi (mikan_bangumi_url) "
        "WHERE mikan_bangumi_url IS NOT NULL AND deleted = 0"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_bangumi_mikan_url")
    with op.batch_alter_table("bangumi") as batch_op:
        batch_op.drop_column("mikan_bangumi_url")
