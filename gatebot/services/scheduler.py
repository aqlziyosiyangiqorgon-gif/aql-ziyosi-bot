"""Scheduled background tasks using APScheduler."""

import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from gatebot.config import Settings
from gatebot.db.crud import get_all_protected_groups, get_all_required_channels
from gatebot.db.session import get_sessionmaker
from gatebot.services.backup import perform_backup
from gatebot.services.notify import notify_admins
from gatebot.utils.html import escape_html

logger = logging.getLogger(__name__)


async def daily_permission_audit(bot: Bot, settings: Settings) -> None:
    """
    Daily audit: verifies bot is still admin and has required rights in all
    active protected groups and required channels. Sends ONE consolidated alert if issues found.
    """
    logger.info("Running daily permissions audit for groups and channels...")
    sessionmaker = get_sessionmaker()
    issues: list[str] = []

    try:
        bot_user = await bot.get_me()
    except Exception as e:
        logger.error("Failed to fetch bot info for audit: %s", e)
        return

    async with sessionmaker() as session:
        groups = await get_all_protected_groups(session, active_only=True)
        channels = await get_all_required_channels(session)

        # 1. Check Protected Groups
        for g in groups:
            try:
                member = await bot.get_chat_member(chat_id=g.chat_id, user_id=bot_user.id)
                if member.status not in ("administrator", "creator"):
                    issues.append(f"• Guruh «{escape_html(g.title)}» (ID: {g.chat_id}): Bot admin emas (status: {member.status})")
                else:
                    can_invite = getattr(member, "can_invite_users", False)
                    if not can_invite:
                        issues.append(f"• Guruh «{escape_html(g.title)}» (ID: {g.chat_id}): So'rovlarni tasdiqlash huquqi yo'q")
            except Exception as err:
                issues.append(f"• Guruh «{escape_html(g.title)}» (ID: {g.chat_id}): Kirishda xatolik ({err})")

        # 2. Check Required Channels
        for ch in channels:
            if not ch.is_active:
                continue
            try:
                member = await bot.get_chat_member(chat_id=ch.chat_id, user_id=bot_user.id)
                if member.status not in ("administrator", "creator"):
                    issues.append(f"• Kanal «{escape_html(ch.title)}» (ID: {ch.chat_id}): Bot admin emas (status: {member.status})")
            except Exception as err:
                issues.append(f"• Kanal «{escape_html(ch.title)}» (ID: {ch.chat_id}): Kirishda xatolik ({err})")

    if issues:
        alert_text = (
            "⚠️ <b>Kunlik tekshiruv: Aniqlangan muammolar!</b>\n\n"
            + "\n".join(issues)
            + "\n\n<i>So'rovlar to'xtab qolmasligi uchun huquqlarni to'g'rilang.</i>"
        )
        logger.warning("Audit discovered %d issues. Sending consolidated alert.", len(issues))
        await notify_admins(bot, settings.ADMIN_IDS, alert_text)
    else:
        logger.info("Daily permissions audit completed cleanly: 0 issues found.")


def setup_scheduler(bot: Bot, settings: Settings) -> AsyncIOScheduler:
    """Configure and return AsyncIOScheduler."""
    scheduler = AsyncIOScheduler(timezone=settings.TIMEZONE)

    # 1. Daily backup at 03:00 Tashkent time
    scheduler.add_job(
        perform_backup,
        trigger=CronTrigger(hour=3, minute=0, timezone=settings.TIMEZONE),
        args=[bot, settings],
        id="daily_backup",
        replace_existing=True,
    )

    # 2. Daily permissions audit at 09:00 Tashkent time
    scheduler.add_job(
        daily_permission_audit,
        trigger=CronTrigger(hour=9, minute=0, timezone=settings.TIMEZONE),
        args=[bot, settings],
        id="daily_permission_audit",
        replace_existing=True,
    )

    return scheduler
