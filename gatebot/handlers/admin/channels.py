"""Admin required channels management."""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from gatebot.db.crud import (
    delete_required_channel,
    get_all_required_channels,
    get_required_channel_by_id,
    set_required_channel_active,
    set_required_channel_url,
)
from gatebot.keyboards.inline import channel_detail_kb, channels_list_kb
from gatebot.texts import ASK_CHANNEL_URL, CHANNEL_URL_SAVED
from gatebot.utils.html import escape_html

router = Router(name="admin_channels")


class ChannelStates(StatesGroup):
    waiting_for_url = State()


@router.callback_query(F.data == "admin_nav:channels")
async def nav_channels(callback: CallbackQuery, session: AsyncSession) -> None:
    channels = await get_all_required_channels(session)
    text = (
        "📢 <b>Majburiy kanallar ro'yxati</b>\n\n"
        "Kanalni sozlash yoki holatini o'zgartirish uchun tanlang:"
    )
    if callback.message:
        await callback.message.edit_text(text, reply_markup=channels_list_kb(channels))
    await callback.answer()


@router.callback_query(F.data.startswith("chn_view:"))
async def view_channel(callback: CallbackQuery, session: AsyncSession) -> None:
    channel_id = int(callback.data.split(":")[1])
    channel = await get_required_channel_by_id(session, channel_id)
    if not channel:
        await callback.answer("Kanal topilmadi", show_alert=True)
        return

    status = "🟢 Faol (tekshiriladi)" if channel.is_active else "🔴 Nofaol"
    url_text = f"<a href='{channel.url}'>{channel.url}</a>" if channel.url else "<i>Mavjud emas</i>"
    text = (
        "📢 <b>Kanal tafsilotlari:</b>\n\n"
        f"• Nomi: <b>{escape_html(channel.title)}</b>\n"
        f"• ID: <code>{channel.chat_id}</code>\n"
        f"• Havola: {url_text}\n"
        f"• Holat: {status}\n"
        f"• Qo'shilgan: {channel.added_at.strftime('%Y-%m-%d %H:%M')}"
    )
    if callback.message:
        await callback.message.edit_text(text, reply_markup=channel_detail_kb(channel))
    await callback.answer()


@router.callback_query(F.data.startswith("chn_toggle:"))
async def toggle_channel(callback: CallbackQuery, session: AsyncSession) -> None:
    channel_id = int(callback.data.split(":")[1])
    channel = await get_required_channel_by_id(session, channel_id)
    if not channel:
        await callback.answer("Kanal topilmadi", show_alert=True)
        return

    new_status = not channel.is_active
    await set_required_channel_active(session, channel.chat_id, new_status)
    channel.is_active = new_status

    status_text = "🟢 Faol holatga o'tkazildi" if new_status else "🔴 Nofaol holatga o'tkazildi"
    await callback.answer(status_text)
    await view_channel(callback, session)


@router.callback_query(F.data.startswith("chn_url:"))
async def edit_channel_url(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    channel_id = int(callback.data.split(":")[1])
    channel = await get_required_channel_by_id(session, channel_id)
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


@router.callback_query(F.data.startswith("chn_del:"))
async def delete_channel_handler(callback: CallbackQuery, session: AsyncSession) -> None:
    channel_id = int(callback.data.split(":")[1])
    channel = await get_required_channel_by_id(session, channel_id)
    if channel:
        await delete_required_channel(session, channel.chat_id)
    await callback.answer("Kanal o'chirildi", show_alert=True)
    await nav_channels(callback, session)
