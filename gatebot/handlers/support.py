"""User support / write to admin ticketing system."""

import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from gatebot.config import Settings
from gatebot.keyboards.inline import (
    SupportCb,
    support_admin_reply_kb,
    support_cancel_kb,
)
from gatebot.utils.html import escape_html

logger = logging.getLogger(__name__)

router = Router(name="support")


class SupportStates(StatesGroup):
    waiting_for_user_message = State()
    waiting_for_admin_reply = State()


@router.callback_query(SupportCb.filter(F.action == "write"))
async def start_user_support(callback: CallbackQuery, state: FSMContext) -> None:
    """Prompt user to write their question or issue."""
    await state.set_state(SupportStates.waiting_for_user_message)
    text = (
        "💬 <b>Qo'llab-quvvatlash xizmati</b>\n\n"
        "Administratorga savol, taklif yoki muammoyingizni yozib qoldiring.\n"
        "<i>Matn, rasm, video, audio yoki fayl yuborishingiz mumkin.</i>"
    )
    if callback.message:
        await callback.message.edit_text(text, reply_markup=support_cancel_kb())
    await callback.answer()


@router.message(SupportStates.waiting_for_user_message)
async def process_user_support_message(
    message: Message,
    state: FSMContext,
    bot: Bot,
    settings: Settings,
) -> None:
    """Forward user message to all administrators."""
    user = message.from_user
    if not user:
        return

    username_str = f"@{escape_html(user.username)}" if user.username else "mavjud emas"
    header = (
        "📬 <b>Yangi murojaat!</b>\n\n"
        f"• Foydalanuvchi: <b>{escape_html(user.full_name)}</b>\n"
        f"• Username: {username_str}\n"
        f"• Telegram ID: <code>{user.id}</code>\n\n"
        "<i>Foydalanuvchi yuborgan xabar:</i>"
    )

    sent_any = False
    for admin_id in settings.ADMIN_IDS:
        try:
            await bot.send_message(chat_id=admin_id, text=header)
            await bot.copy_message(
                chat_id=admin_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
                reply_markup=support_admin_reply_kb(user_id=user.id),
            )
            sent_any = True
        except Exception as e:
            logger.error("Could not forward support message to admin %d: %s", admin_id, e)

    await state.clear()
    if sent_any:
        await message.answer("✅ Murojaatingiz administratorga yuborildi. Tez orada javob olasiz!")
    else:
        await message.answer("⚠️ Xabarni yuborishda xatolik yuz berdi. Iltimos, keyinroq qayta urinib ko'ring.")


from gatebot.db.models import BotUser


@router.callback_query(SupportCb.filter(F.action == "reply"))
async def start_admin_reply(
    callback: CallbackQuery,
    callback_data: SupportCb,
    state: FSMContext,
    session: AsyncSession | None = None,
    bot: Bot | None = None,
) -> None:
    """Admin clicks 'Javob berish' button."""
    target_user_id = callback_data.user_id
    await state.update_data(target_user_id=target_user_id)
    await state.set_state(SupportStates.waiting_for_admin_reply)

    user_name = "Foydalanuvchi"
    username = None

    if session is not None:
        try:
            db_user = await session.get(BotUser, target_user_id)
            if db_user:
                user_name = db_user.first_name or user_name
                username = db_user.username
        except Exception:
            pass

    if not username and bot is not None:
        try:
            chat_info = await bot.get_chat(target_user_id)
            user_name = chat_info.full_name or user_name
            username = chat_info.username
        except Exception:
            pass

    user_link = f"<a href=\"tg://user?id={target_user_id}\">{escape_html(user_name)}</a>"
    username_info = f" (@{escape_html(username)})" if username else ""

    text = (
        f"✍️ {user_link}{username_info} (ID: <code>{target_user_id}</code>) ga yuboriladigan javobingizni yozing:\n\n"
        "<i>Matn, rasm, video, audio yoki fayl yuborishingiz mumkin.</i>"
    )
    if callback.message:
        await callback.message.reply(text, reply_markup=support_cancel_kb())
    await callback.answer()


@router.message(SupportStates.waiting_for_admin_reply)
async def process_admin_reply(
    message: Message,
    state: FSMContext,
    bot: Bot,
) -> None:
    """Send admin's reply back to the user."""
    data = await state.get_data()
    target_user_id = data.get("target_user_id")

    if not target_user_id:
        await message.answer("⚠️ Foydalanuvchi topilmadi.")
        await state.clear()
        return

    try:
        await bot.send_message(
            chat_id=target_user_id,
            text="💬 <b>Administrator javobi:</b>",
        )
        await bot.copy_message(
            chat_id=target_user_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
        )
        await message.answer(f"✅ Javob <code>{target_user_id}</code> ga muvaffaqiyatli yetkazildi!")
    except Exception as e:
        logger.error("Failed to send reply to user %d: %s", target_user_id, e)
        await message.answer("❌ Javobni yetkazishda xatolik yuz berdi (foydalanuvchi botni bloklagan bo'lishi mumkin).")

    await state.clear()


@router.callback_query(SupportCb.filter(F.action == "cancel"))
async def cancel_support_action(callback: CallbackQuery, state: FSMContext) -> None:
    """Cancel support FSM action."""
    await state.clear()
    if callback.message:
        await callback.message.edit_text("❌ Bekor qilindi.")
    await callback.answer("Bekor qilindi")
