"""add bot users table

Revision ID: 002_bot_users
Revises: 001_initial
Create Date: 2026-09-26 18:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002_bot_users"
down_revision: str | None = "001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bot_users",
        sa.Column("tg_id", sa.BigInteger(), nullable=False),
        sa.Column("first_name", sa.String(length=255), nullable=True),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("is_bot_blocked", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("tg_id"),
    )


def downgrade() -> None:
    op.drop_table("bot_users")
