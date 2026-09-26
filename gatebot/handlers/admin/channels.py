"""Admin required channels management with manual add, URL update, and reordering."""

import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from gatebot.db.crud import (
    add_or_update_required_channel,
    delete_required_channel,
    get_all_required_channels,
    get_required_channel_by_chat_id,
    get_required_channel_by_id,
    set_required_channel_active,
    set_required_channel_url,
    update_channel_sort_order,
)
from gatebot.keyboards.inline import (
    ChannelCb,
    NavCb,
    channel_detail_kb,
    channels_list_kb,
)
from gatebot.texts import ASK_CHANNEL_URL, CHANNEL_URL_SAVED
from gatebot.utils.html import escape_html

logger = logging.getLogger(__name__)

router = Router(name="admin_channels")


class ChannelStates(StatesGroup):
    waiting_for_url = State()
    waiting_for_channel = State()


@router.callback_query(NavCb.filter(F.target == "channels"))
async def nav_channels(callback: CallbackQuery, session: AsyncSession) -> None:
    channels = await get_all_required_channels(session)
    text = (
        "📢 <b>Majburiy kanallar ro'yxati</b>\n\n"
        "Kanalni sozlash, tartibini o'zgartirish yoki yangi kanal qo'shish uchun tanlang:"
    )
    if callback.message:
        await callback.message.edit_text(text, reply_markup=channels_list_kb(channels))
    await callback.answer()


@router.callback_query(ChannelCb.filter(F.action == "view"))
async def view_channel(callback: CallbackQuery, callback_data: ChannelCb, session: AsyncSession) -> None:
    channel = await get_required_channel_by_id(session, callback_data.channel_id)
    if not channel:
        await callback.answer("Kanal topilmadi", show_alert=True)
        return

    status = "🟢 Faol (tekshiriladi)" if channel.is_active else "🔴 Nofaol"
    url_text = f"<a href='{channel.url}'>{channel.url}</a>" if channel.url else "<i>Mavjud emas</i>"
    text = (
        f"📢 <b>Kanal tafsilotlari:</b>\n\n"
        f"• Nomi: <b>{escape_html(channel.title)}</b>\n"
        f"• ID: <code>{channel.chat_id}</code>\n"
        f"• Havola: {url_text}\n"
        f"• Tartib raqami: <b>{channel.sort_order}</b>\n"
        f"• Holat: {status}\n"
        f"• Qo'shilgan: {channel.added_at.strftime('%Y-%m-%d %H:%M')}"
    )
    if callback.message:
        await callback.message.edit_text(text, reply_markup=channel_detail_kb(channel))
    await callback.answer()


@router.callback_query(ChannelCb.filter(F.action == "toggle"))
async def toggle_channel(callback: CallbackQuery, callback_data: ChannelCb, session: AsyncSession) -> None:
    channel = await get_required_channel_by_id(session, callback_data.channel_id)
    if not channel:
        await callback.answer("Kanal topilmadi", show_alert=True)
        return

    new_status = not channel.is_active
    await set_required_channel_active(session, channel.chat_id, new_status)
    channel.is_active = new_status

    status_text = "🟢 Faol holatga o'tkazildi" if new_status else "🔴 Nofaol holatga o'tkazildi"
    await callback.answer(status_text)
    await view_channel(callback, callback_data, session)


@router.callback_query(ChannelCb.filter(F.action == "up"))
async def move_channel_up(callback: CallbackQuery, callback_data: ChannelCb, session: AsyncSession) -> None:
    await update_channel_sort_order(session, callback_data.channel_id, delta=1)
    await callback.answer("Tartib oshirildi (+1)")
    await view_channel(callback, callback_data, session)


@router.callback_query(ChannelCb.filter(F.action == "down"))
async def move_channel_down(callback: CallbackQuery, callback_data: ChannelCb, session: AsyncSession) -> None:
    await update_channel_sort_order(session, callback_data.channel_id, delta=-1)
    await callback.answer("Tartib kamaytirildi (-1)")
    await view_channel(callback, callback_data, session)


@router.callback_query(ChannelCb.filter(F.action == "url"))
async def edit_channel_url(callback: CallbackQuery, callback_data: ChannelCb, state: FSMContext, session: AsyncSession) -> None:
    channel = await get_required_channel_by_id(session, callback_data.channel_id)
    if not channel:
        await callback.answer("Kanal topilmadi", show_alert=True)
        return

    await state.update_data(channel_chat_id=channel.chat_id, channel_title=channel.title)
    await state.set_state(ChannelStates.waiting_for_url)
    if callback.message:
        await callback.message.edit_text(ASK_CHANNEL_URL.format(title=escape_html(channel.title)))
    await callback.answer()


@router.message(ChannelStates.waiting_for_url)
async def process_channel_url_input(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    url = (message.text or "").strip()
    data = await state.get_data()
    chat_id = data["channel_chat_id"]
    title = data["channel_title"]

    await set_required_channel_url(session, chat_id, url)
    await state.clear()
    await message.answer(CHANNEL_URL_SAVED.format(title=escape_html(title), url=url))


@router.callback_query(ChannelCb.filter(F.action == "del"))
async def delete_channel_handler(
    callback: CallbackQuery, callback_data: ChannelCb, session: AsyncSession
) -> None:
    channel = await get_required_channel_by_id(session, callback_data.channel_id)
    if channel:
        await delete_required_channel(session, channel.chat_id)
    await callback.answer("Kanal o'chirildi", show_alert=True)
    await nav_channels(callback, session)


# --- Manual Add Flow ---
@router.callback_query(ChannelCb.filter(F.action == "add"))
async def start_manual_add_channel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ChannelStates.waiting_for_channel)
    text = (
        "➕ <b>Kanalni qo'lda qo'shish</b>\n\n"
        "Kanalning <code>@username</code>ini, sonli ID raqamini kiriting yoki kanaldan biror xabarni shu yerga forward qiling:\n\n"
        "<i>Eslatma: Bot avval o'sha kanalga admin qilib qo'shilgan bo'lishi kerak.</i>"
    )
    if callback.message:
        await callback.message.edit_text(text)
    await callback.answer()


@router.message(ChannelStates.waiting_for_channel)
async def process_manual_channel_input(
    message: Message, state: FSMContext, bot: Bot, session: AsyncSession
) -> None:
    chat_identifier = None
    if message.forward_from_chat and message.forward_from_chat.type == "channel":
        chat_identifier = message.forward_from_chat.id
    elif message.text:
        txt = message.text.strip()
        if txt.startswith("@") or txt.lstrip("-").isdigit():
            chat_identifier = int(txt) if txt.lstrip("-").isdigit() else txt

    if not chat_identifier:
        await message.answer("⚠️ Yaroqsiz ma'lumot. Iltimos @username, ID kiriting yoki kanaldan xabar forward qiling:")
        return

    try:
        tg_chat = await bot.get_chat(chat_identifier)
        bot_user = await bot.get_me()
        member = await bot.get_chat_member(chat_id=tg_chat.id, user_id=bot_user.id)
        if member.status not in ("administrator", "creator"):
            await message.answer("❌ Bot ushbu kanalda administrator emas! Avval botni admin qiling.")
            return

        existing = await get_required_channel_by_chat_id(session, tg_chat.id)
        if existing:
            await state.clear()
            await message.answer(f"ℹ️ «{escape_html(existing.title)}» kanali allaqachon ro'yxatga olingan.")
            return

        url = f"https://t.me/{tg_chat.username}" if tg_chat.username else tg_chat.invite_link
        title = tg_chat.title or "Kanal"

        try:
            await add_or_update_required_channel(session, chat_id=tg_chat.id, title=title, url=url)
        except IntegrityError:
            await session.rollback()
            await message.answer("ℹ️ Ushbu kanal allaqachon ro'yxatga olingan.")
            await state.clear()
            return

        await state.clear()
        res_msg = f"✅ «{escape_html(title)}» kanali muvaffaqiyatli majburiy kanallar safiga qo'shildi!"
        if not url:
            res_msg += "\n\n💡 <i>Eslatma: Kanal yopiq. Foydalanuvchilar o'tishi uchun havola (URL) kiritishni unutmang.</i>"
        await message.answer(res_msg)

    except Exception as e:
        logger.error("Error manually adding channel %s: %s", chat_identifier, e)
        await message.answer(f"❌ Kanalni tekshirishda xatolik yuz berdi: {e}")
