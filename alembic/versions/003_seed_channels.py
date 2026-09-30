"""Seed required channel @qorgonyangi

Revision ID: 003_seed_channels
Revises: 002_bot_users
Create Date: 2026-09-30 14:00:00.000000

"""
from datetime import datetime, timezone
import sqlalchemy as sa
from alembic import op

revision = "003_seed_channels"
down_revision = "002_bot_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM required_channels"))
    now = datetime.now(timezone.utc)
    conn.execute(
        sa.text(
            "INSERT INTO required_channels (chat_id, title, url, is_active, sort_order, added_at) "
            "VALUES (:chat_id, :title, :url, :is_active, :sort_order, :added_at)"
        ),
        {
            "chat_id": -1004375773849,
            "title": "Aql ziyosi",
            "url": "https://t.me/qorgonyangi",
            "is_active": True,
            "sort_order": 1,
            "added_at": now,
        },
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM required_channels WHERE chat_id = -1004375773849"))
