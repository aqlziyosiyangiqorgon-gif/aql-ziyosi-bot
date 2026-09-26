"""initial tables

Revision ID: 001_initial
Revises: None
Create Date: 2026-09-26 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "protected_groups",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("protected_groups", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_protected_groups_chat_id"), ["chat_id"], unique=True)

    op.create_table(
        "required_channels",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("url", sa.String(length=512), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("required_channels", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_required_channels_chat_id"), ["chat_id"], unique=True)

    op.create_table(
        "admins",
        sa.Column("tg_id", sa.BigInteger(), nullable=False),
        sa.Column("added_by", sa.BigInteger(), nullable=True),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("tg_id"),
    )

    op.create_table(
        "join_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("user_name", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("missing_channels", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["protected_groups.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("join_events", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_join_events_group_id"), ["group_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_join_events_user_id"), ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_table("join_events")
    op.drop_table("admins")
    op.drop_table("required_channels")
    op.drop_table("protected_groups")
