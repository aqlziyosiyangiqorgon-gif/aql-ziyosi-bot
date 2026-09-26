"""Chat join request handler (Core Gatekeeper Feature)."""

import logging

from aiogram import Bot, Router
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
)
from aiogram.types import ChatJoinRequest
from sqlalchemy.ext.asyncio import AsyncSession

from gatebot.config import Settings
from gatebot.db.crud import (
    get_active_required_channels,
    get_protected_group_by_chat_id,
    log_join_event,
)
from gatebot.keyboards.inline import missing_channels_kb
from gatebot.services.subscription import check_user
from gatebot.texts import APPROVE_DM, DECLINE_DM
from gatebot.utils.html import escape_html

logger = logging.getLogger(__name__)

router = Router(name="join_requests")


@router.chat_join_request()
async def process_chat_join_request(
    request: ChatJoinRequest,
    bot: Bot,
    session: AsyncSession,
    settings: Settings,
) -> None:
    """
    Handle incoming chat join request:
    1. Look up group in protected_groups. If not found or is_active=False -> ignore.
    2. Run check_user against active required channels.
    3. If ok -> approve request, DM user with APPROVE_DM, log join event.
    4. If not ok -> decline request, DM user with DECLINE_DM + links, log join event.
    """
    group_chat_id = request.chat.id
    user_id = request.from_user.id
    user_name = request.from_user.full_name

    logger.info(
        "Received join request: user %d (%s) -> chat %d (%s)",
        user_id,
        user_name,
        group_chat_id,
        request.chat.title,
    )

    # 1. Check if group is protected
    group = await get_protected_group_by_chat_id(session, group_chat_id)
    if not group or not group.is_active:
        logger.debug("Chat %d is not a managed protected group. Ignoring request.", group_chat_id)
        return

    # 2. Check active required channels
    channels = await get_active_required_channels(session)
    result = await check_user(
        bot=bot,
        user_id=user_id,
        channels=channels,
        admin_ids=settings.ADMIN_IDS,
        cache_ttl=settings.SUB_CACHE_SECONDS,
    )

    if result.ok:
        # 3. Approved
        logger.info("Approving join request for user %d to group %d", user_id, group_chat_id)
        try:
            await bot.approve_chat_join_request(chat_id=group_chat_id, user_id=user_id)
        except (TelegramBadRequest, TelegramForbiddenError, TelegramNetworkError, TelegramRetryAfter) as e:
            logger.error("Failed to approve join request for user %d: %s", user_id, e)

        # DM user (ignore failure if user blocked bot)
        try:
            text = APPROVE_DM.format(group_title=escape_html(request.chat.title))
            await bot.send_message(chat_id=request.user_chat_id, text=text)
        except Exception as dm_err:
            logger.debug("Could not send approval DM to user %d: %s", user_id, dm_err)

        # Audit log
        await log_join_event(
            session=session,
            group_id=group.id,
            user_id=user_id,
            user_name=user_name,
            status="approved",
            missing_channels=None,
        )

    else:
        # 4. Declined
        logger.info(
            "Declining join request for user %d to group %d (missing %d channels)",
            user_id,
            group_chat_id,
            len(result.missing),
        )
        try:
            await bot.decline_chat_join_request(chat_id=group_chat_id, user_id=user_id)
        except (TelegramBadRequest, TelegramForbiddenError, TelegramNetworkError, TelegramRetryAfter) as e:
            logger.error("Failed to decline join request for user %d: %s", user_id, e)

        # DM user with missing channels
        channel_lines: list[str] = []
        for ch in result.missing:
            channel_lines.append(f"• <b>{escape_html(ch.title)}</b>")

        channels_text = "\n".join(channel_lines)
        decline_text = DECLINE_DM.format(channels=channels_text)
        kb = missing_channels_kb(result.missing)

        try:
            await bot.send_message(
                chat_id=request.user_chat_id,
                text=decline_text,
                reply_markup=kb,
            )
        except Exception as dm_err:
            logger.debug("Could not send decline DM to user %d: %s", user_id, dm_err)

        # Audit log
        missing_titles = ", ".join([ch.title for ch in result.missing])
        await log_join_event(
            session=session,
            group_id=group.id,
            user_id=user_id,
            user_name=user_name,
            status="declined",
            missing_channels=missing_titles,
        )
