"""Admin broadcast message handler with FSM and media support."""

import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from gatebot.db.crud import get_all_admins, get_all_protected_groups, get_all_required_channels, get_broadcast_counts
from gatebot.keyboards.inline import (
    BroadcastCb,
    NavCb,
    admin_main_menu_kb,
    broadcast_confirm_kb,
    broadcast_target_kb,
)
from gatebot.services.broadcast import send_broadcast
from gatebot.utils.html import safe_edit_text

logger = logging.getLogger(__name__)

router = Router(name="admin_broadcast")


class BroadcastStates(StatesGroup):
    waiting_for_target = State()
    waiting_for_message = State()
    confirm = State()


@router.callback_query(NavCb.filter(F.target == "broadcast"))
async def start_broadcast(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Show broadcast target selection."""
    await state.clear()
    counts = await get_broadcast_counts(session)
    text = (
        "✉️ <b>Xabar yuborish (Broadcast)</b>\n\n"
        "Xabarni kimlarga yubormoqchisiz? Kerakli qabul qiluvchilarni tanlang:\n\n"
        f"• Shaxsiy foydalanuvchilar: <b>{counts['users']}</b> ta\n"
        f"• Himoyalangan guruhlar: <b>{counts['groups']}</b> ta"
    )
    if callback.message:
        await safe_edit_text(
            callback.message,
            text,
            reply_markup=broadcast_target_kb(
                users_count=counts["users"], groups_count=counts["groups"]
            ),
        )
    await state.set_state(BroadcastStates.waiting_for_target)
    await callback.answer()


@router.callback_query(BroadcastCb.filter(F.action == "target"))
async def process_target_selection(
    callback: CallbackQuery,
    callback_data: BroadcastCb,
    state: FSMContext,
) -> None:
    """Process chosen broadcast recipient target."""
    target = callback_data.target
    await state.update_data(target=target)
    await state.set_state(BroadcastStates.waiting_for_message)

    target_labels = {
        "users": "Faqat foydalanuvchilar",
        "groups": "Faqat guruhlar",
        "all": "Barchaga (Foydalanuvchilar + Guruhlar)",
    }
    label = target_labels.get(target, "Barchaga")

    text = (
        f"🎯 Tanlangan yo'nalish: <b>{label}</b>\n\n"
        "✍️ <b>Endi yuboriladigan xabarni jo'nating:</b>\n"
        "<i>Matn, rasm, video, audio, hujjat yoki boshqa kanaldan forward xabar yuborishingiz mumkin.</i>"
    )
    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data=BroadcastCb(action="cancel").pack())]
        ]
    )
    if callback.message:
        await safe_edit_text(callback.message, text, reply_markup=cancel_kb)
    await callback.answer()


@router.message(BroadcastStates.waiting_for_message)
async def process_broadcast_message(
    message: Message,
    state: FSMContext,
) -> None:
    """Save message for broadcast and ask for confirmation."""
    data = await state.get_data()
    target = data.get("target", "all")

    await state.update_data(
        from_chat_id=message.chat.id,
        message_id=message.message_id,
    )
    await state.set_state(BroadcastStates.confirm)

    target_labels = {
        "users": "Faqat foydalanuvchilar (shaxsiy)",
        "groups": "Faqat himoyalangan guruhlar",
        "all": "Barchaga (Foydalanuvchilar + Guruhlar)",
    }
    label = target_labels.get(target, "Barchaga")

    confirm_text = (
        "☝️ <b>Xabaringiz qabul qilindi!</b>\n\n"
        f"• Qabul qiluvchilar: <b>{label}</b>\n\n"
        "Haqiqatan ham ushbu xabarni barcha tanlangan qabul qiluvchilarga tarqatishni tasdiqlaysizmi?"
    )
    await message.answer(confirm_text, reply_markup=broadcast_confirm_kb())


@router.callback_query(BroadcastCb.filter(F.action == "send"))
async def execute_broadcast(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    session: AsyncSession,
) -> None:
    """Execute broadcast asynchronously with rate-limiting."""
    data = await state.get_data()
    target = data.get("target", "all")
    from_chat_id = data.get("from_chat_id")
    message_id = data.get("message_id")

    if not from_chat_id or not message_id:
        await callback.answer("⚠️ Xatolik: xabar topilmadi.", show_alert=True)
        await state.clear()
        return

    if callback.message:
        await safe_edit_text(callback.message, "⏳ <b>Xabar tarqatilmoqda, iltimos kuting...</b>")

    stats = await send_broadcast(
        bot=bot,
        session=session,
        target_type=target,
        from_chat_id=from_chat_id,
        message_id=message_id,
    )

    report_text = (
        "✅ <b>Xabar tarqatish yakunlandi!</b>\n\n"
        "📊 <b>Natijalar:</b>\n"
        f"• Jami qabul qiluvchilar: <b>{stats.total}</b> ta\n"
        f"• Muvaffaqiyatli yetkazildi: <b>{stats.delivered}</b> ta\n"
        f"• Bloklagan / ruxsatsiz: <b>{stats.blocked}</b> ta\n"
        f"• Boshqa xatoliklar: <b>{stats.failed}</b> ta"
    )
    back_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Bosh menyu", callback_data=NavCb(target="main").pack())]
        ]
    )
    if callback.message:
        await safe_edit_text(callback.message, report_text, reply_markup=back_kb)
    await state.clear()
    await callback.answer()


@router.callback_query(BroadcastCb.filter(F.action == "cancel"))
async def cancel_broadcast(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Cancel broadcast and return to admin main menu."""
    await state.clear()
    groups = await get_all_protected_groups(session)
    channels = await get_all_required_channels(session)
    admins = await get_all_admins(session)
    kb = admin_main_menu_kb(
        groups_count=len(groups),
        channels_count=len(channels),
        admins_count=len(admins),
    )
    if callback.message:
        await safe_edit_text(
            callback.message,
            "❌ Xabar yuborish bekor qilindi.\n\n⚙️ <b>Administrator paneli</b>\n\nKerakli bo'limni tanlang:",
            reply_markup=kb,
        )
    await callback.answer("Bekor qilindi")
