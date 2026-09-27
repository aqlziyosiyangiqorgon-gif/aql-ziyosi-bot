"""Chat join request handler (Core Gatekeeper Feature)."""

import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
)
from aiogram.types import CallbackQuery, ChatJoinRequest
from sqlalchemy.ext.asyncio import AsyncSession

from gatebot.config import Settings
from gatebot.db.crud import (
    add_or_update_user,
    get_active_required_channels,
    get_protected_group_by_chat_id,
    log_join_event,
)
from gatebot.keyboards.inline import CheckSubCb, missing_channels_kb
from gatebot.services.subscription import check_user
from gatebot.texts import APPROVE_DM, DECLINE_DM
from gatebot.utils.html import escape_html, safe_edit_text

logger = logging.getLogger(__name__)

router = Router(name="join_requests")


async def get_group_invite_url(bot: Bot, chat_id: int) -> str | None:
    """Fetch or export invite link for the chat."""
    try:
        chat = await bot.get_chat(chat_id)
        if chat.username:
            return f"https://t.me/{chat.username}"
        if chat.invite_link:
            return chat.invite_link
        return await bot.export_chat_invite_link(chat_id)
    except Exception as e:
        logger.debug("Could not get chat link for %d: %s", chat_id, e)
        return None


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
    4. If not ok -> keep request pending, DM user with DECLINE_DM + links + Obuna bo'ldim button, log event.
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

    # Track user for broadcasts
    await add_or_update_user(
        session,
        tg_id=user_id,
        first_name=request.from_user.first_name,
        username=request.from_user.username,
    )

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
        # 3. Approved immediately
        logger.info("Approving join request for user %d to group %d", user_id, group_chat_id)
        try:
            await bot.approve_chat_join_request(chat_id=group_chat_id, user_id=user_id)
        except (TelegramBadRequest, TelegramForbiddenError, TelegramNetworkError, TelegramRetryAfter) as e:
            logger.error("Failed to approve join request for user %d: %s", user_id, e)

        # Resolve group link
        group_link = await get_group_invite_url(bot, group_chat_id)
        if group_link:
            group_display = f"<a href=\"{group_link}\">«{escape_html(request.chat.title)}»</a>"
            from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
            reply_kb = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text=f"➡️ {request.chat.title} guruhiga kirish", url=group_link)]]
            )
        else:
            group_display = f"«{escape_html(request.chat.title)}»"
            reply_kb = None

        # DM user (ignore failure if user blocked bot)
        try:
            text = APPROVE_DM.format(group_title=group_display)
            await bot.send_message(chat_id=request.user_chat_id, text=text, reply_markup=reply_kb)
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
        # 4. User missing required channels: keep request pending and send DM with channels & check button
        logger.info(
            "User %d missing %d channels for group %d. Leaving pending and sending DM.",
            user_id,
            len(result.missing),
            group_chat_id,
        )

        # DM user with missing channels
        channel_lines: list[str] = []
        for ch in result.missing:
            channel_lines.append(f"• <b>{escape_html(ch.title)}</b>")

        channels_text = "\n".join(channel_lines)
        decline_text = DECLINE_DM.format(channels=channels_text)
        kb = missing_channels_kb(result.missing, group_chat_id=group_chat_id)

        try:
            await bot.send_message(
                chat_id=request.user_chat_id,
                text=decline_text,
                reply_markup=kb,
            )
        except Exception as dm_err:
            logger.debug("Could not send decline DM to user %d: %s", user_id, dm_err)

        # Audit log
        missing_titles = " || ".join([ch.title for ch in result.missing])
        await log_join_event(
            session=session,
            group_id=group.id,
            user_id=user_id,
            user_name=user_name,
            status="pending",
            missing_channels=missing_titles,
        )


@router.callback_query(CheckSubCb.filter())
async def on_check_subscription(
    callback: CallbackQuery,
    callback_data: CheckSubCb,
    bot: Bot,
    session: AsyncSession,
    settings: Settings,
) -> None:
    """Handle '✅ Obuna bo'ldim' button click."""
    user = callback.from_user
    if not user:
        return

    group_chat_id = callback_data.group_chat_id
    group = await get_protected_group_by_chat_id(session, group_chat_id)
    if not group or not group.is_active:
        await callback.answer("⚠️ Guruh nofaol yoki tizimda topilmadi.", show_alert=True)
        return

    channels = await get_active_required_channels(session)
    result = await check_user(
        bot=bot,
        user_id=user.id,
        channels=channels,
        admin_ids=settings.ADMIN_IDS,
        cache_ttl=settings.SUB_CACHE_SECONDS,
    )

    if result.ok:
        try:
            await bot.approve_chat_join_request(chat_id=group_chat_id, user_id=user.id)

            # Resolve group link
            group_link = await get_group_invite_url(bot, group_chat_id)
            if group_link:
                group_display = f"<a href=\"{group_link}\">«{escape_html(group.title)}»</a>"
                from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
                reply_kb = InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text=f"➡️ {group.title} guruhiga kirish", url=group_link)]]
                )
            else:
                group_display = f"«{escape_html(group.title)}»"
                reply_kb = None

            if callback.message:
                await safe_edit_text(
                    callback.message,
                    APPROVE_DM.format(group_title=group_display),
                    reply_markup=reply_kb,
                )
            await callback.answer("✅ Tabriklaymiz! Siz guruhga muvaffaqiyatli qabul qilindingiz.", show_alert=True)

            await log_join_event(
                session=session,
                group_id=group.id,
                user_id=user.id,
                user_name=user.full_name,
                status="approved",
                missing_channels=None,
            )
        except TelegramBadRequest as e:
            err_msg = str(e).lower()
            if "hide_requester_missing" in err_msg or "user_not_found" in err_msg or "request_already" in err_msg:
                # Join request eskirgan — foydalanuvchiga guruh havolasini beramiz
                group_link = await get_group_invite_url(bot, group_chat_id)
                if group_link:
                    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
                    link_kb = InlineKeyboardMarkup(
                        inline_keyboard=[[InlineKeyboardButton(text=f"➡️ {group.title} guruhiga kirish", url=group_link)]]
                    )
                    expired_text = (
                        f"⚠️ Guruhga kirish so'rovingiz eskirgan.\n\n"
                        f"✅ Siz barcha kanallarga obuna bo'lgansiz! Quyidagi tugma orqali "
                        f"<a href=\"{group_link}\">«{escape_html(group.title)}»</a> guruhiga to'g'ridan-to'g'ri kirishingiz mumkin:"
                    )
                    if callback.message:
                        await safe_edit_text(callback.message, expired_text, reply_markup=link_kb)
                    await callback.answer("✅ Obuna tasdiqlandi! Guruhga havola orqali kiring.", show_alert=True)
                else:
                    await callback.answer(
                        "⚠️ Guruhga kirish so'rovingiz eskirgan. Guruh havolasi orqali qayta kirish so'rovini yuboring.",
                        show_alert=True,
                    )
            else:
                logger.error("Failed to approve join request on check: %s", e)
                await callback.answer("❌ Guruhga qo'shishda xatolik yuz berdi. Qaytadan urinib ko'ring.", show_alert=True)
        except Exception as e:
            logger.error("Unexpected error approving join request on check: %s", e)
            await callback.answer("❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.", show_alert=True)
    else:
        channel_lines: list[str] = [f"• <b>{escape_html(ch.title)}</b>" for ch in result.missing]
        channels_text = "\n".join(channel_lines)
        decline_text = DECLINE_DM.format(channels=channels_text)
        kb = missing_channels_kb(result.missing, group_chat_id=group_chat_id)
        if callback.message:
            await safe_edit_text(callback.message, decline_text, reply_markup=kb)

        await callback.answer(
            "❌ Hali barcha kanallarga a'zo bo'lmadingiz! Iltimos, barcha kanallarga a'zo bo'lib, so'ng qayta tekshiring.",
            show_alert=True,
        )
