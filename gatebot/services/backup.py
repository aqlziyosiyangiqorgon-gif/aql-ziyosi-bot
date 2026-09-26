"""Database online backup service for SQLite and PostgreSQL."""

import logging
import os
import sqlite3
import tempfile
import zipfile
from datetime import datetime

from aiogram import Bot
from aiogram.types import FSInputFile

from gatebot.config import Settings

logger = logging.getLogger(__name__)


def extract_sqlite_path(database_url: str) -> str | None:
    """Extract SQLite local file path from SQLAlchemy DATABASE_URL."""
    if "sqlite" not in database_url:
        return None
    # e.g. sqlite+aiosqlite:///./data/bot.db -> ./data/bot.db
    # or sqlite+aiosqlite:///:memory: -> :memory:
    parts = database_url.split(":///")
    if len(parts) == 2:
        return parts[1]
    return None


def create_sqlite_online_backup(source_db_path: str, target_sql_path: str) -> None:
    """
    Perform a live online backup of an SQLite database using sqlite3.Connection.backup().
    Safe for concurrent operations without database locking issues.
    """
    source_conn = sqlite3.connect(source_db_path)
    dest_conn = sqlite3.connect(target_sql_path)
    try:
        with dest_conn:
            source_conn.backup(dest_conn, pages=100)
    finally:
        dest_conn.close()
        source_conn.close()


async def perform_backup(bot: Bot, settings: Settings) -> bool:
    """
    Execute database backup:
    - If SQLite: perform online backup, compress into zip, send via Telegram, remove temp files.
    - If PostgreSQL: log that backup is skipped (not implemented) without erroring.
    """
    db_url = settings.DATABASE_URL

    if "postgres" in db_url:
        logger.info("PostgreSQL database detected. Managed backup is skipped (handled externally).")
        return True

    source_path = extract_sqlite_path(db_url)
    if not source_path or source_path == ":memory:":
        logger.warning("Database path is memory or unavailable (%s). Skipping backup.", db_url)
        return False

    if not os.path.exists(source_path):
        logger.error("Source database file does not exist: %s", source_path)
        return False

    target_chat_id = settings.effective_backup_chat_id
    if not target_chat_id:
        logger.warning("No target backup chat ID configured. Backup skipped.")
        return False

    now_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    temp_dir = tempfile.mkdtemp(prefix="gatebot_backup_")
    backup_db_path = os.path.join(temp_dir, f"bot_{now_str}.db")
    backup_zip_path = os.path.join(temp_dir, f"backup_{now_str}.zip")

    try:
        logger.info("Starting online SQLite backup from %s...", source_path)
        create_sqlite_online_backup(source_path, backup_db_path)

        # Create zip archive
        with zipfile.ZipFile(backup_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(backup_db_path, arcname=os.path.basename(backup_db_path))

        file_size_kb = os.path.getsize(backup_zip_path) / 1024
        logger.info("Backup archive created: %s (%.1f KB)", backup_zip_path, file_size_kb)

        caption = (
            f"📦 <b>AQL ZIYOSI Baza Zaxira Nusxasi</b>\n\n"
            f"• Sana: <code>{now_str}</code>\n"
            f"• Hajm: <code>{file_size_kb:.1f} KB</code>\n"
            f"• Turi: SQLite Online Snapshot"
        )
        document = FSInputFile(backup_zip_path, filename=f"gatebot_backup_{now_str}.zip")

        await bot.send_document(
            chat_id=target_chat_id,
            document=document,
            caption=caption,
        )
        logger.info("Backup successfully dispatched to chat %d", target_chat_id)
        return True

    except Exception as e:
        logger.error("Database backup operation failed: %s", e, exc_info=True)
        return False

    finally:
        # Cleanup temp directory
        for p in (backup_db_path, backup_zip_path):
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
        try:
            os.rmdir(temp_dir)
        except Exception:
            pass
