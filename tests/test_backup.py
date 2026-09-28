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


def test_restore_sqlite_database_valid_and_invalid():
    """Verify restore_sqlite_database handles valid .db, .zip, and invalid files."""
    import zipfile
    from gatebot.services.backup import restore_sqlite_database

    temp_dir = tempfile.mkdtemp()
    try:
        sample_db = os.path.join(temp_dir, "sample.db")
        target_db = os.path.join(temp_dir, "restored.db")
        target_url = f"sqlite+aiosqlite:///{target_db}"

        # Create valid sqlite
        conn = sqlite3.connect(sample_db)
        with conn:
            conn.execute("CREATE TABLE users (id INT, name TEXT)")
            conn.execute("INSERT INTO users VALUES (1, 'Ali')")
        conn.close()

        with open(sample_db, "rb") as f:
            raw_bytes = f.read()

        # 1. Test valid .db restore
        ok, msg = restore_sqlite_database(raw_bytes, target_url)
        assert ok is True
        assert os.path.exists(target_db)

        # Check restored data
        r_conn = sqlite3.connect(target_db)
        row = r_conn.execute("SELECT name FROM users WHERE id = 1").fetchone()
        r_conn.close()
        assert row == ("Ali",)

        # 2. Test valid .zip restore
        zip_path = os.path.join(temp_dir, "backup.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.write(sample_db, arcname="bot.db")
        with open(zip_path, "rb") as f:
            zip_bytes = f.read()

        ok, msg = restore_sqlite_database(zip_bytes, target_url)
        assert ok is True

        # 3. Test invalid corrupted content
        ok, err = restore_sqlite_database(b"NOT A SQLITE FILE DATA AT ALL", target_url)
        assert ok is False
        assert "haqiqiy SQLite" in err
    finally:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)

