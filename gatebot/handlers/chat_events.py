"""Chat events and automatic detection via my_chat_member & migrations."""

import logging

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.filters.chat_member_updated import (
    ADMINISTRATOR,
    IS_NOT_MEMBER,
    MEMBER,
    RESTRICTED,
    ChatMemberUpdatedFilter,
)
from aiogram.types import CallbackQuery, ChatMemberUpdated, Message
from sqlalchemy.ext.asyncio import AsyncSession

from gatebot.config import Settings
from gatebot.db.crud import (
    add_or_update_protected_group,
    add_or_update_required_channel,
    get_protected_group_by_chat_id,
    get_required_channel_by_chat_id,
    is_admin,
    set_protected_group_active,
    set_required_channel_active,
    update_protected_group_chat_id,
)
from gatebot.keyboards.inline import channel_confirm_kb, group_confirm_kb
from gatebot.services.notify import (
    notify_bot_removed,
    notify_non_admin_add,
)
from gatebot.texts import (
    CHANNEL_IGNORED,
    CHANNEL_SAVED,
    GROUP_IGNORED,
    GROUP_SAVED,
    LEFT_NON_ADMIN_ADD,
    NEW_CHANNEL_DETECTED,
    NEW_GROUP_DETECTED,
    WARN_NO_INVITE_PERMISSION,
)
from gatebot.utils.html import escape_html

logger = logging.getLogger(__name__)

router = Router(name="chat_events")


# 1. Bot becomes ADMINISTRATOR
@router.my_chat_member(
    ChatMemberUpdatedFilter(
        member_status_changed=(IS_NOT_MEMBER | MEMBER | RESTRICTED) >> ADMINISTRATOR
    )
)
async def on_bot_promoted_to_admin(
    event: ChatMemberUpdated,
    bot: Bot,
    session: AsyncSession,
    settings: Settings,
) -> None:
    """Handle bot added or promoted to admin in a group or channel."""
    chat = event.chat
    inviter = event.from_user
    new_member = event.new_chat_member

    logger.info(
        "Bot promoted to admin in %s (%s, ID: %d) by %s (ID: %d)",
        chat.type,
        chat.title,
        chat.id,
        inviter.full_name,
        inviter.id,
    )

    # Verify if inviter is an authorized admin
    user_is_adm = await is_admin(session, inviter.id, settings.ADMIN_IDS)
    if not user_is_adm:
        logger.warning(
            "Bot was added by non-admin user %d to %s %d. Leaving chat.",
            inviter.id,
            chat.type,
            chat.id,
        )
        try:
            if chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
                await bot.send_message(chat_id=chat.id, text=LEFT_NON_ADMIN_ADD)
            await bot.leave_chat(chat.id)
        except Exception as e:
            logger.error("Failed to leave unauthorized chat %d: %s", chat.id, e)

        await notify_non_admin_add(
            bot=bot,
            admin_ids=settings.ADMIN_IDS,
            chat_title=chat.title or "Noma'lum",
            chat_id=chat.id,
            user_id=inviter.id,
        )
        return

    # Inviter IS an admin:
    if chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        # Check invite permission
        can_invite = getattr(new_member, "can_invite_users", False)
        if not can_invite:
            try:
                warn_text = WARN_NO_INVITE_PERMISSION.format(title=escape_html(chat.title))
                await bot.send_message(chat_id=inviter.id, text=warn_text)
            except Exception as e:
                logger.debug("Could not DM permission warning to admin %d: %s", inviter.id, e)

        # Send confirmation prompt
        prompt_text = NEW_GROUP_DETECTED.format(title=escape_html(chat.title))
        kb = group_confirm_kb(chat.id)
        try:
            await bot.send_message(chat_id=inviter.id, text=prompt_text, reply_markup=kb)
        except Exception as e:
            logger.error("Could not send group confirmation prompt to admin %d: %s", inviter.id, e)

    elif chat.type == ChatType.CHANNEL:
        prompt_text = NEW_CHANNEL_DETECTED.format(title=escape_html(chat.title))
        kb = channel_confirm_kb(chat.id)
        try:
            await bot.send_message(chat_id=inviter.id, text=prompt_text, reply_markup=kb)
        except Exception as e:
            logger.error("Could not send channel confirmation prompt to admin %d: %s", inviter.id, e)


# 2. Bot REMOVED or demoted from admin
@router.my_chat_member(
    ChatMemberUpdatedFilter(
        member_status_changed=ADMINISTRATOR >> (IS_NOT_MEMBER | MEMBER | RESTRICTED)
    )
)
async def on_bot_removed_or_demoted(
    event: ChatMemberUpdated,
    bot: Bot,
    session: AsyncSession,
    settings: Settings,
) -> None:
    """Handle bot demoted or kicked from a protected group or required channel."""
    chat = event.chat
    logger.info("Bot removed or demoted in %s (%d)", chat.title, chat.id)

    # Check protected groups
    group = await get_protected_group_by_chat_id(session, chat.id)
    if group and group.is_active:
        await set_protected_group_active(session, chat.id, False)
        await notify_bot_removed(
            bot=bot,
            admin_ids=settings.ADMIN_IDS,
            chat_title=chat.title or "Guruh",
            chat_id=chat.id,
            chat_type="guruhi",
        )

    # Check required channels
    channel = await get_required_channel_by_chat_id(session, chat.id)
    if channel and channel.is_active:
        await set_required_channel_active(session, chat.id, False)
        await notify_bot_removed(
            bot=bot,
            admin_ids=settings.ADMIN_IDS,
            chat_title=chat.title or "Kanal",
            chat_id=chat.id,
            chat_type="kanali",
        )


# 3. Supergroup Migration
@router.message(F.migrate_to_chat_id)
async def on_group_migration(
    message: Message,
    session: AsyncSession,
) -> None:
    """Handle basic group migration to supergroup."""
    old_id = message.chat.id
    new_id = message.migrate_to_chat_id
    if not new_id:
        return

    logger.info("Group migrated from %d to supergroup %d", old_id, new_id)
    await update_protected_group_chat_id(session, old_chat_id=old_id, new_chat_id=new_id)


# 4. Auto-delete service messages (new members joined, left) in protected groups
@router.message(F.new_chat_members | F.left_chat_member)
async def on_service_join_leave_message(
    message: Message,
    session: AsyncSession,
) -> None:
    """Auto-delete 'user joined/left group' service messages in managed groups."""
    group = await get_protected_group_by_chat_id(session, message.chat.id)
    if not group or not group.is_active:
        return

    try:
        await message.delete()
        logger.debug("Deleted join/leave service message in group %d", message.chat.id)
    except Exception as e:
        logger.debug("Could not delete service message in group %d: %s", message.chat.id, e)


# 4. Confirmation callbacks from DM prompts
@router.callback_query(F.data.startswith("group_add:"))
async def on_group_confirm(
    callback: CallbackQuery, bot: Bot, session: AsyncSession, settings: Settings
) -> None:
    if not callback.from_user or not await is_admin(session, callback.from_user.id, settings.ADMIN_IDS):
        await callback.answer("⛔️ Ruxsat yo'q", show_alert=True)
        return

    try:
        chat_id = int((callback.data or "").split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("⚠️ Yaroqsiz so'rov.", show_alert=True)
        return

    try:
        tg_chat = await bot.get_chat(chat_id)
        title = tg_chat.title or "Noma'lum guruh"
    except Exception:
        title = "Guruh"

    await add_or_update_protected_group(session, chat_id=chat_id, title=title)
    if callback.message:
        await callback.message.edit_text(GROUP_SAVED.format(title=escape_html(title)))
    await callback.answer()


@router.callback_query(F.data.startswith("group_reject:"))
async def on_group_reject(
    callback: CallbackQuery, bot: Bot, session: AsyncSession, settings: Settings
) -> None:
    if not callback.from_user or not await is_admin(session, callback.from_user.id, settings.ADMIN_IDS):
        await callback.answer("⛔️ Ruxsat yo'q", show_alert=True)
        return

    try:
        chat_id = int((callback.data or "").split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("⚠️ Yaroqsiz so'rov.", show_alert=True)
        return

    try:
        tg_chat = await bot.get_chat(chat_id)
        title = tg_chat.title or "Guruh"
    except Exception:
        title = "Guruh"

    if callback.message:
        await callback.message.edit_text(GROUP_IGNORED.format(title=escape_html(title)))
    await callback.answer()


@router.callback_query(F.data.startswith("chan_add:"))
async def on_channel_confirm(
    callback: CallbackQuery, bot: Bot, session: AsyncSession, settings: Settings
) -> None:
    if not callback.from_user or not await is_admin(session, callback.from_user.id, settings.ADMIN_IDS):
        await callback.answer("⛔️ Ruxsat yo'q", show_alert=True)
        return

    try:
        chat_id = int((callback.data or "").split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("⚠️ Yaroqsiz so'rov.", show_alert=True)
        return

    invite_url = None
    try:
        tg_chat = await bot.get_chat(chat_id)
        title = tg_chat.title or "Noma'lum kanal"
        if tg_chat.username:
            invite_url = f"https://t.me/{tg_chat.username}"
        elif tg_chat.invite_link:
            invite_url = tg_chat.invite_link
    except Exception:
        title = "Kanal"

    await add_or_update_required_channel(session, chat_id=chat_id, title=title, url=invite_url)
    msg = CHANNEL_SAVED.format(title=escape_html(title))
    if not invite_url:
        msg += "\n\n💡 <i>Eslatma: Kanal yopiq (private). Foydalanuvchilarga havola ko'rinishi uchun /admin orqali havola qo'shing.</i>"
    if callback.message:
        await callback.message.edit_text(msg)
    await callback.answer()


@router.callback_query(F.data.startswith("chan_reject:"))
async def on_channel_reject(
    callback: CallbackQuery, bot: Bot, session: AsyncSession, settings: Settings
) -> None:
    if not callback.from_user or not await is_admin(session, callback.from_user.id, settings.ADMIN_IDS):
        await callback.answer("⛔️ Ruxsat yo'q", show_alert=True)
        return

    try:
        chat_id = int((callback.data or "").split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("⚠️ Yaroqsiz so'rov.", show_alert=True)
        return

    try:
        tg_chat = await bot.get_chat(chat_id)
        title = tg_chat.title or "Kanal"
    except Exception:
        title = "Kanal"

    if callback.message:
        await callback.message.edit_text(CHANNEL_IGNORED.format(title=escape_html(title)))
    await callback.answer()

