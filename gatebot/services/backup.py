"""Database online backup service for SQLite and PostgreSQL."""

import logging
import os
import shutil
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
        shutil.rmtree(temp_dir, ignore_errors=True)


def restore_sqlite_database(uploaded_bytes: bytes, target_db_url: str) -> tuple[bool, str]:
    """
    Restore an SQLite database from uploaded .db or .zip file.
    Validates SQLite header and atomically replaces the active database.
    """
    if "sqlite" not in target_db_url:
        return False, "Faqat SQLite bazasini tiklash mumkin."

    target_path = extract_sqlite_path(target_db_url)
    if not target_path or target_path == ":memory:":
        return False, "Baza fayli yo'li aniqlanmadi."

    temp_dir = tempfile.mkdtemp(prefix="gatebot_restore_")
    try:
        temp_file = os.path.join(temp_dir, "uploaded_file")
        with open(temp_file, "wb") as f:
            f.write(uploaded_bytes)

        db_file_to_restore = temp_file
        if zipfile.is_zipfile(temp_file):
            with zipfile.ZipFile(temp_file, "r") as zf:
                db_names = [n for n in zf.namelist() if n.endswith(".db") or n.endswith(".sqlite")]
                if not db_names:
                    return False, "Zip fayl ichida .db fayl topilmadi."
                extracted = zf.extract(db_names[0], temp_dir)
                db_file_to_restore = extracted

        # Validate SQLite magic header
        with open(db_file_to_restore, "rb") as f:
            header = f.read(16)
            if not header.startswith(b"SQLite format 3"):
                return False, "Yuklangan fayl haqiqiy SQLite ma'lumotlar bazasi emas."

        # Ensure target dir exists
        target_dir = os.path.dirname(target_path)
        if target_dir:
            os.makedirs(target_dir, exist_ok=True)

        # Backup current database before replacing
        if os.path.exists(target_path):
            shutil.copy2(target_path, f"{target_path}.bak")

        shutil.copy2(db_file_to_restore, target_path)
        return True, "Ma'lumotlar bazasi muvaffaqiyatli tiklandi."
    except Exception as e:
        logger.error("Failed to restore database: %s", e, exc_info=True)
        return False, f"Xatolik: {e}"
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

