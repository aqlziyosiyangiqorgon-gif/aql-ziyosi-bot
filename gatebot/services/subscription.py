"""Subscription verification service with caching and fail-closed handling."""

import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.types import ChatMemberRestricted

from gatebot.db.models import RequiredChannel
from gatebot.services.notify import notify_channel_access_lost

logger = logging.getLogger(__name__)

# In-memory cache for positive subscription checks: (user_id, channel_chat_id) -> expiry timestamp
_positive_cache: dict[tuple[int, int], float] = {}


@dataclass
class SubscriptionResult:
    """Result of membership verification."""

    ok: bool
    missing: list[RequiredChannel]


def clear_cache() -> None:
    """Clear positive cache (primarily for tests)."""
    _positive_cache.clear()


async def check_user(
    bot: Bot,
    user_id: int,
    channels: Sequence[RequiredChannel],
    admin_ids: list[int] | None = None,
    cache_ttl: int = 60,
) -> SubscriptionResult:
    """
    Check if user is a member of ALL active required channels.

    Rules:
    - Member if status in {creator, administrator, member} OR (status == restricted AND is_member True).
    - Left / kicked / banned / restricted with is_member False -> not a member.
    - Caches ONLY positive results for `cache_ttl` seconds. Never caches negatives.
    - If Telegram API call fails (bot not admin, chat not found): FAIL CLOSED (treat as missing)
      and notify admins (rate-limited to 30 mins).
    - If channels is empty: returns ok=True immediately.
    """
    if not channels:
        logger.warning("No active required channels configured. Bypassing check for user %d.", user_id)
        return SubscriptionResult(ok=True, missing=[])

    missing: list[RequiredChannel] = []
    now = time.monotonic()

    for channel in channels:
        cache_key = (user_id, channel.chat_id)
        cached_expiry = _positive_cache.get(cache_key)

        if cached_expiry and cached_expiry > now:
            logger.debug("Cache hit for user %d in channel %d", user_id, channel.chat_id)
            continue

        try:
            member = await bot.get_chat_member(chat_id=channel.chat_id, user_id=user_id)
            is_sub = False

            if member.status in (
                ChatMemberStatus.CREATOR,
                ChatMemberStatus.ADMINISTRATOR,
                ChatMemberStatus.MEMBER,
            ):
                is_sub = True
            elif member.status == ChatMemberStatus.RESTRICTED:
                if isinstance(member, ChatMemberRestricted) and member.is_member:
                    is_sub = True
                elif getattr(member, "is_member", False):
                    is_sub = True

            if is_sub:
                _positive_cache[cache_key] = now + cache_ttl
            else:
                missing.append(channel)

        except Exception as e:
            # FAIL CLOSED: treat as not a member, add to missing, alert admins
            logger.error(
                "Error checking membership for user %d in channel %s (%d): %s",
                user_id,
                channel.title,
                channel.chat_id,
                e,
            )
            missing.append(channel)
            if admin_ids:
                try:
                    await notify_channel_access_lost(
                        bot=bot,
                        admin_ids=admin_ids,
                        channel_title=channel.title,
                        channel_chat_id=channel.chat_id,
                    )
                except Exception as notify_err:
                    logger.error("Failed to trigger access lost alert: %s", notify_err)

    return SubscriptionResult(ok=(len(missing) == 0), missing=missing)
