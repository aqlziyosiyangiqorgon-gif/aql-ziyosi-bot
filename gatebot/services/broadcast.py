"""Asynchronous broadcast service with rate limiting and status reporting."""

import asyncio
import logging
from dataclasses import dataclass
from typing import Literal

from aiogram import Bot
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)
from sqlalchemy.ext.asyncio import AsyncSession

from gatebot.db.crud import (
    get_active_broadcast_users,
    get_all_protected_groups,
    set_protected_group_active,
    set_user_blocked,
)

logger = logging.getLogger(__name__)

TargetType = Literal["users", "groups", "all"]


@dataclass
class BroadcastStats:
    total: int = 0
    delivered: int = 0
    blocked: int = 0
    failed: int = 0


async def send_broadcast(
    bot: Bot,
    session: AsyncSession,
    target_type: TargetType,
    from_chat_id: int,
    message_id: int,
) -> BroadcastStats:
    """
    Broadcast a message to target recipients using bot.copy_message.
    Safe rate limiting: 0.04s between sends (~25 msgs/sec).
    """
    stats = BroadcastStats()
    recipient_chat_ids: list[int] = []

    if target_type in ("users", "all"):
        users = await get_active_broadcast_users(session)
        recipient_chat_ids.extend([u.tg_id for u in users])

    if target_type in ("groups", "all"):
        groups = await get_all_protected_groups(session, active_only=True)
        recipient_chat_ids.extend([g.chat_id for g in groups])

    stats.total = len(recipient_chat_ids)
    if stats.total == 0:
        return stats

    for chat_id in recipient_chat_ids:
        try:
            await bot.copy_message(
                chat_id=chat_id,
                from_chat_id=from_chat_id,
                message_id=message_id,
            )
            stats.delivered += 1
        except TelegramRetryAfter as e:
            logger.warning("Broadcast hit rate limit, waiting %s seconds", e.retry_after)
            await asyncio.sleep(e.retry_after)
            try:
                await bot.copy_message(
                    chat_id=chat_id,
                    from_chat_id=from_chat_id,
                    message_id=message_id,
                )
                stats.delivered += 1
            except Exception as retry_err:
                logger.error("Failed retry broadcast to %d: %s", chat_id, retry_err)
                stats.failed += 1
        except TelegramForbiddenError:
            # User blocked the bot or bot removed from group
            stats.blocked += 1
            if chat_id > 0:
                await set_user_blocked(session, chat_id, is_blocked=True)
            else:
                await set_protected_group_active(session, chat_id, is_active=False)
        except TelegramBadRequest as e:
            logger.warning("TelegramBadRequest broadcasting to %d: %s", chat_id, e)
            stats.failed += 1
        except Exception as e:
            logger.error("Unexpected error broadcasting to %d: %s", chat_id, e)
            stats.failed += 1

        # Rate-limiting pause (25 msgs / sec)
        await asyncio.sleep(0.04)

    return stats
