"""Backup service unit tests."""

import os
import sqlite3
import tempfile
from unittest.mock import AsyncMock

import pytest

from gatebot.config import Settings
from gatebot.services.backup import (
    create_sqlite_online_backup,
    extract_sqlite_path,
    perform_backup,
)


def test_extract_sqlite_path():
    assert extract_sqlite_path("sqlite+aiosqlite:///./data/bot.db") == "./data/bot.db"
    assert extract_sqlite_path("sqlite+aiosqlite:///C:/data/bot.db") == "C:/data/bot.db"
    assert extract_sqlite_path("postgresql+asyncpg://user:pass@localhost/db") is None


def test_create_sqlite_online_backup():
    """Verify online backup produces a consistent, readable SQLite database."""
    temp_dir = tempfile.mkdtemp()
    source_db = os.path.join(temp_dir, "source.db")
    backup_db = os.path.join(temp_dir, "backup.db")

    # Create source database with table and records
    conn = sqlite3.connect(source_db)
    with conn:
        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, val TEXT)")
        conn.execute("INSERT INTO test (val) VALUES ('hello'), ('world')")
    conn.close()

    # Perform online backup
    create_sqlite_online_backup(source_db, backup_db)
    assert os.path.exists(backup_db)

    # Verify backup database contains the data
    b_conn = sqlite3.connect(backup_db)
    cur = b_conn.cursor()
    rows = cur.execute("SELECT val FROM test ORDER BY id").fetchall()
    b_conn.close()

    assert rows == [("hello",), ("world",)]

    # Cleanup
    os.remove(source_db)
    os.remove(backup_db)
    os.rmdir(temp_dir)


@pytest.mark.asyncio
async def test_perform_backup_sqlite():
    """Verify perform_backup zips the database and sends it as document."""
    temp_dir = tempfile.mkdtemp()
    source_db = os.path.join(temp_dir, "source.db")

    conn = sqlite3.connect(source_db)
    with conn:
        conn.execute("CREATE TABLE test (id INT)")
    conn.close()

    settings = Settings(
        BOT_TOKEN="123:ABC",
        ADMIN_IDS=[111, 222],
        DATABASE_URL=f"sqlite+aiosqlite:///{source_db}",
        BACKUP_CHAT_ID=999,
    )

    mock_bot = AsyncMock()
    success = await perform_backup(mock_bot, settings)
    assert success is True

    # Check send_document called
    mock_bot.send_document.assert_called_once()
    call_kwargs = mock_bot.send_document.call_args[1]
    assert call_kwargs["chat_id"] == 999
    assert "Baza Zaxira Nusxasi" in call_kwargs["caption"]
    assert call_kwargs["document"].filename.endswith(".zip")

    # Cleanup
    os.remove(source_db)
    os.rmdir(temp_dir)


@pytest.mark.asyncio
async def test_perform_backup_postgres_skip():
    """Verify PostgreSQL skips backup cleanly without errors."""
    settings = Settings(
        BOT_TOKEN="123:ABC",
        ADMIN_IDS=[111],
        DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db",
    )
    mock_bot = AsyncMock()
    success = await perform_backup(mock_bot, settings)
    assert success is True
    mock_bot.send_document.assert_not_called()
