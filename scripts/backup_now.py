"""Standalone manual backup script for gatebot."""

import asyncio
import logging
import sys

from gatebot.config import load_settings
from gatebot.main import create_bot
from gatebot.services.backup import perform_backup

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    settings = load_settings()
    bot = create_bot(settings.BOT_TOKEN)
    logger.info("Running standalone manual backup...")
    try:
        success = await perform_backup(bot, settings)
        if success:
            logger.info("Backup completed successfully.")
        else:
            logger.error("Backup failed.")
            sys.exit(1)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
