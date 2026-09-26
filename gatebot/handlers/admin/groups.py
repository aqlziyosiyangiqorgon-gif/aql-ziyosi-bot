"""Admin protected groups management with manual add and permissions check."""

import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from gatebot.db.crud import (
    add_or_update_protected_group,
    delete_protected_group,
    get_all_protected_groups,
    get_protected_group_by_chat_id,
    get_protected_group_by_id,
    set_protected_group_active,
)
from gatebot.keyboards.inline import (
    GroupCb,
    NavCb,
    group_detail_kb,
    groups_list_kb,
)
from gatebot.utils.html import escape_html, safe_edit_text

logger = logging.getLogger(__name__)

router = Router(name="admin_groups")


class ManualGroupStates(StatesGroup):
    waiting_for_chat = State()


@router.callback_query(NavCb.filter(F.target == "groups"))
async def nav_groups(callback: CallbackQuery, session: AsyncSession) -> None:
    groups = await get_all_protected_groups(session)
    text = (
        "👥 <b>Himoyalangan guruhlar</b>\n\n"
        "Guruh holatini o'zgartirish, huquqlarni tekshirish yoki yangi qo'shish uchun tanlang:"
    )
    if callback.message:
        await safe_edit_text(callback.message, text, reply_markup=groups_list_kb(groups))
    await callback.answer()


@router.callback_query(GroupCb.filter(F.action == "view"))
async def view_group(callback: CallbackQuery, callback_data: GroupCb, session: AsyncSession) -> None:
    group = await get_protected_group_by_id(session, callback_data.group_id)
    if not group:
        await callback.answer("Guruh topilmadi", show_alert=True)
        return

    status = "🟢 Faol (so'rovlar tekshiriladi)" if group.is_active else "🔴 Nofaol (o'chirilgan)"
    text = (
        f"🛡 <b>Guruh tafsilotlari:</b>\n\n"
        f"• Nomi: <b>{escape_html(group.title)}</b>\n"
        f"• ID: <code>{group.chat_id}</code>\n"
        f"• Holat: {status}\n"
        f"• Qo'shilgan: {group.added_at.strftime('%Y-%m-%d %H:%M')}"
    )
    if callback.message:
        await safe_edit_text(callback.message, text, reply_markup=group_detail_kb(group))
    await callback.answer()


@router.callback_query(GroupCb.filter(F.action == "check"))
async def check_group_rights(
    callback: CallbackQuery, callback_data: GroupCb, bot: Bot, session: AsyncSession
) -> None:
    """Verify bot admin permissions and invite users right in the group."""
    group = await get_protected_group_by_id(session, callback_data.group_id)
    if not group:
        await callback.answer("Guruh topilmadi", show_alert=True)
        return

    try:
        bot_user = await bot.get_me()
        member = await bot.get_chat_member(chat_id=group.chat_id, user_id=bot_user.id)
        if member.status not in ("administrator", "creator"):
            await callback.answer("❌ Bot ushbu guruhda admin emas!", show_alert=True)
            return

        can_invite = getattr(member, "can_invite_users", False)
        if can_invite:
            await callback.answer("✅ Barcha huquqlar joyida! Bot so'rovlarni boshqara oladi.", show_alert=True)
        else:
            await callback.answer(
                "⚠️ Bot admin, lekin «Approve new members» / «Invite users» huquqiga ega emas!",
                show_alert=True,
            )
    except Exception as e:
        await callback.answer(f"⚠️ Xatolik yuz berdi: {e}", show_alert=True)


@router.callback_query(GroupCb.filter(F.action == "toggle"))
async def toggle_group(callback: CallbackQuery, callback_data: GroupCb, session: AsyncSession) -> None:
    group = await get_protected_group_by_id(session, callback_data.group_id)
    if not group:
        await callback.answer("Guruh topilmadi", show_alert=True)
        return

    new_status = not group.is_active
    await set_protected_group_active(session, group.chat_id, new_status)
    group.is_active = new_status

    status_text = "🟢 Faol holatga o'tkazildi" if new_status else "🔴 Nofaol holatga o'tkazildi"
    await callback.answer(status_text)
    await view_group(callback, callback_data, session)


@router.callback_query(GroupCb.filter(F.action == "del"))
async def delete_group_handler(
    callback: CallbackQuery, callback_data: GroupCb, session: AsyncSession
) -> None:
    group = await get_protected_group_by_id(session, callback_data.group_id)
    if group:
        await delete_protected_group(session, group.chat_id)
    await callback.answer("Guruh ro'yxatdan o'chirildi", show_alert=True)
    await nav_groups(callback, session)


# --- Manual Add Flow ---
@router.callback_query(GroupCb.filter(F.action == "add"))
async def start_manual_add_group(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ManualGroupStates.waiting_for_chat)
    text = (
        "➕ <b>Guruhni qo'lda qo'shish</b>\n\n"
        "Guruhning sonli ID raqamini kiriting (masalan, <code>-1001234567890</code>) "
        "yoki o'sha guruhdan biror xabarni shu yerga forward qiling:\n\n"
        "<i>Eslatma: Bot avval o'sha guruhga admin qilib qo'shilgan bo'lishi kerak.</i>"
    )
    if callback.message:
        await safe_edit_text(callback.message, text)
    await callback.answer()


@router.message(ManualGroupStates.waiting_for_chat)
async def process_manual_group_input(
    message: Message, state: FSMContext, bot: Bot, session: AsyncSession
) -> None:
    chat_id = None
    if message.forward_from_chat and message.forward_from_chat.type in ("group", "supergroup"):
        chat_id = message.forward_from_chat.id
    elif message.text and message.text.strip().lstrip("-").isdigit():
        chat_id = int(message.text.strip())

    if not chat_id:
        await message.answer("⚠️ Yaroqsiz guruh ID. Iltimos, sonli ID kiriting yoki guruhdan xabar forward qiling:")
        return

    # Check already registered
    existing = await get_protected_group_by_chat_id(session, chat_id)
    if existing:
        await state.clear()
        await message.answer(f"ℹ️ «{escape_html(existing.title)}» guruhi allaqachon ro'yxatga olingan.")
        return

    # Verify bot is admin there
    try:
        bot_user = await bot.get_me()
        member = await bot.get_chat_member(chat_id=chat_id, user_id=bot_user.id)
        if member.status not in ("administrator", "creator"):
            await message.answer("❌ Bot ushbu guruhda administrator emas! Avval botni admin qiling.")
            return

        tg_chat = await bot.get_chat(chat_id)
        title = tg_chat.title or "Guruh"

        try:
            await add_or_update_protected_group(session, chat_id=chat_id, title=title)
        except IntegrityError:
            await session.rollback()
            await message.answer("ℹ️ Ushbu guruh allaqachon ro'yxatga olingan.")
            await state.clear()
            return

        await state.clear()
        await message.answer(f"✅ «{escape_html(title)}» guruhi muvaffaqiyatli himoyalangan guruhlarga qo'shildi!")

    except Exception as e:
        logger.error("Error manually adding group %d: %s", chat_id, e)
        await message.answer(f"❌ Guruhni tekshirishda xatolik: {e}")
