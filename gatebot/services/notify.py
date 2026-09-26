"""Admin notification service with rate limiting."""

import logging
import time

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

logger = logging.getLogger(__name__)

# In-memory cooldown cache: key -> monotonic timestamp
_alert_history: dict[str, float] = {}
RATE_LIMIT_SECONDS = 1800  # 30 minutes


def _is_rate_limited(key: str, cooldown: float = RATE_LIMIT_SECONDS) -> bool:
    now = time.monotonic()
    last_time = _alert_history.get(key)
    if last_time and (now - last_time < cooldown):
        return True
    _alert_history[key] = now
    return False


def clear_alert_history() -> None:
    """Clear alert history (primarily for tests)."""
    _alert_history.clear()


async def notify_admins(
    bot: Bot,
    admin_ids: list[int],
    text: str,
) -> None:
    """Send message to all administrators safely."""
    for admin_id in admin_ids:
        try:
            await bot.send_message(chat_id=admin_id, text=text)
        except TelegramAPIError as e:
            logger.warning("Failed to send alert to admin %d: %s", admin_id, e)
        except Exception as e:
            logger.error("Unexpected error notifying admin %d: %s", admin_id, e)


async def notify_channel_access_lost(
    bot: Bot,
    admin_ids: list[int],
    channel_title: str,
    channel_chat_id: int,
) -> bool:
    """Notify admins when bot loses access to a required channel (rate-limited to 30 min)."""
    key = f"channel_access_lost:{channel_chat_id}"
    if _is_rate_limited(key):
        logger.info("Channel %d access lost notification suppressed by rate limit", channel_chat_id)
        return False

    text = (
        f"⚠️ <b>Ogohlantirish!</b> Bot «{channel_title}» (ID: <code>{channel_chat_id}</code>) "
        f"kanaliga kirish huquqini yo'qotdi. Foydalanuvchilar a'zoligini tekshirish to'xtab qolmasligi "
        f"uchun bot adminlik huquqlarini tekshiring!"
    )
    await notify_admins(bot, admin_ids, text)
    return True


async def notify_bot_removed(
    bot: Bot,
    admin_ids: list[int],
    chat_title: str,
    chat_id: int,
    chat_type: str,
) -> None:
    """Notify admins when bot is kicked or demoted from group or channel."""
    text = (
        f"ℹ️ Bot «{chat_title}» (ID: <code>{chat_id}</code>) {chat_type}idan chiqarildi "
        f"yoki adminlikdan olindi. Ushbu ob'ekt nofaol (is_active=False) holatiga o'tkazildi."
    )
    await notify_admins(bot, admin_ids, text)


async def notify_non_admin_add(
    bot: Bot,
    admin_ids: list[int],
    chat_title: str,
    chat_id: int,
    user_id: int,
) -> None:
    """Notify admins when non-admin tries to add bot to a group."""
    text = (
        f"⚠️ Noma'lum foydalanuvchi (ID: <code>{user_id}</code>) botni «{chat_title}» "
        f"(ID: <code>{chat_id}</code>) guruhiga qo'shishga urindi. Bot guruhdan chiqib ketdi."
    )
    await notify_admins(bot, admin_ids, text)


async def notify_system_error(
    bot: Bot,
    admin_ids: list[int],
    error_text: str,
) -> None:
    """Notify admins about unhandled system errors (rate-limited per error type)."""
    key = f"system_error:{error_text[:40]}"
    if _is_rate_limited(key, cooldown=300):
        return
    text = f"🔥 <b>Tizimda xatolik yuz berdi:</b>\n<pre>{error_text[:3000]}</pre>"
    await notify_admins(bot, admin_ids, text)
