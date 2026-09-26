"""Main application entry point for Gatekeeper Bot."""

import asyncio
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent

from gatebot.config import Settings, load_settings
from gatebot.db.migrations import run_upgrade_head
from gatebot.db.session import dispose_engine, init_engine
from gatebot.handlers import chat_events, join_requests, start
from gatebot.handlers.admin import admin_router
from gatebot.middlewares.db_session import DbSessionMiddleware
from gatebot.services.notify import notify_system_error
from gatebot.services.scheduler import setup_scheduler

logger = logging.getLogger(__name__)


def setup_logging(log_level: str = "INFO") -> None:
    """Configure console and rotating file logging."""
    os.makedirs("logs", exist_ok=True)
    level = getattr(logging, log_level.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    file_handler = RotatingFileHandler(
        filename=os.path.join("logs", "bot.log"),
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)


def setup_directories() -> None:
    """Ensure runtime data and log directories exist."""
    os.makedirs("data", exist_ok=True)
    os.makedirs("logs", exist_ok=True)


def create_bot(token: str) -> Bot:
    """Create and return Bot instance with HTML default parse mode."""
    return Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher(settings: Settings) -> Dispatcher:
    """Create and configure Dispatcher with middlewares and routers."""
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Provide global settings to all events
    dp["settings"] = settings

    # Outer middleware for database session
    dp.update.outer_middleware(DbSessionMiddleware())

    # Include routers
    dp.include_router(start.router)
    dp.include_router(admin_router)
    dp.include_router(join_requests.router)
    dp.include_router(chat_events.router)

    return dp


def register_global_error_handler(
    dp: Dispatcher, bot: Bot, admin_ids: list[int]
) -> None:
    """Register global error handler for aiogram."""

    @dp.errors()
    async def global_error_handler(event: ErrorEvent) -> bool:
        logger.error(
            "Unhandled exception: %s",
            event.exception,
            exc_info=event.exception,
        )
        if isinstance(event.exception, Exception):
            try:
                await notify_system_error(bot, admin_ids, str(event.exception))
            except Exception as e:
                logger.error("Failed to dispatch error notification: %s", e)
        return True


async def start_bot(settings: Settings, bot: Bot, dp: Dispatcher) -> None:
    """Initialize DB migrations, verify bot token, start scheduler, and start polling."""
    logger.info("Initializing AQL ZIYOSI Join Request Gatekeeper Bot...")
    setup_directories()

    # 1. Run migrations
    logger.info("Running database migrations...")
    try:
        run_upgrade_head()
    except Exception as e:
        logger.exception("Database migration failed: %s", e)
        raise

    # 2. Init DB engine
    init_engine(settings.DATABASE_URL)

    # 3. Verify Bot Token
    try:
        bot_info = await bot.get_me()
        logger.info(
            "Bot verified successfully: @%s (id: %d, token: %s)",
            bot_info.username,
            bot_info.id,
            settings.masked_token,
        )
    except Exception as e:
        logger.error("Failed to verify bot token with Telegram: %s", e)
        raise

    # 4. Global error handler
    register_global_error_handler(dp, bot, settings.ADMIN_IDS)

    # 5. Start background jobs scheduler
    scheduler = setup_scheduler(bot, settings)
    scheduler.start()
    logger.info("Scheduler started with timezone %s", settings.TIMEZONE)

    try:
        # 6. Polling with explicitly resolved update types
        used_updates = dp.resolve_used_update_types()
        critical_updates = {"message", "callback_query", "chat_join_request", "my_chat_member"}
        allowed_updates = list(set(used_updates).union(critical_updates))

        logger.info("Starting polling with allowed_updates=%s", allowed_updates)
        await dp.start_polling(bot, allowed_updates=allowed_updates)
    finally:
        logger.info("Stopping scheduler...")
        scheduler.shutdown(wait=False)


async def main() -> None:
    """Application CLI entry point."""
    try:
        settings = load_settings()
    except Exception as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)

    setup_logging(settings.LOG_LEVEL)
    bot = create_bot(settings.BOT_TOKEN)
    dp = create_dispatcher(settings)

    try:
        await start_bot(settings, bot, dp)
    finally:
        logger.info("Shutting down bot gracefully...")
        await bot.session.close()
        await dispose_engine()
        logger.info("Shutdown completed.")


if __name__ == "__main__":
    asyncio.run(main())
