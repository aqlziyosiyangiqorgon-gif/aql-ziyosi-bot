"""Admin required channels management with manual add, URL update, and reordering."""

import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
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
from gatebot.utils.html import escape_html, safe_edit_text

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
        await safe_edit_text(callback.message, text, reply_markup=channels_list_kb(channels))
    await callback.answer()


@router.callback_query(ChannelCb.filter(F.action == "view"))
async def view_channel(callback: CallbackQuery, callback_data: ChannelCb, session: AsyncSession) -> None:
    channel = await get_required_channel_by_id(session, callback_data.channel_id)
    if not channel:
        await callback.answer("Kanal topilmadi", show_alert=True)
        return

    status = "🟢 Faol (tekshiriladi)" if channel.is_active else "🔴 Nofaol"
    url_text = f"<a href='{escape_html(channel.url)}'>{escape_html(channel.url)}</a>" if channel.url else "<i>Mavjud emas</i>"
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
        await safe_edit_text(callback.message, text, reply_markup=channel_detail_kb(channel))
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
async def edit_channel_url(callback: CallbackQuery, callback_data: ChannelCb, bot: Bot, session: AsyncSession) -> None:
    channel = await get_required_channel_by_id(session, callback_data.channel_id)
    if not channel:
        await callback.answer("Kanal topilmadi", show_alert=True)
        return

    new_link = None
    try:
        created = await bot.create_chat_invite_link(
            chat_id=channel.chat_id,
            name="A'zolik havolasi",
        )
        new_link = created.invite_link
    except Exception as e:
        logger.warning("Could not auto-generate channel invite link for %d: %s", channel.chat_id, e)
        try:
            tg_chat = await bot.get_chat(channel.chat_id)
            if tg_chat.username:
                new_link = f"https://t.me/{tg_chat.username}"
        except Exception:
            pass

    if new_link:
        await set_required_channel_url(session, channel.chat_id, new_link)
        channel.url = new_link
        await callback.answer("✅ Yangi havola tayyor!", show_alert=False)
        await view_channel(callback, callback_data, session)
        if callback.message:
            await callback.message.answer(
                f"🔗 «<b>{escape_html(channel.title)}</b>» kanali uchun ishlaydigan havola:\n\n"
                f"👉 <code>{new_link}</code>\n\n"
                f"<i>(Ustiga bossangiz, havola avtomatik nusxalanadi)</i>"
            )
    else:
        await callback.answer("❌ Havolani avtomatik olib bo'lmadi. Bot kanalda admin ekanligini tekshiring.", show_alert=True)



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
        "➕ <b>Kanal yoki guruhni qo'lda qo'shish</b>\n\n"
        "Kanal/guruhning <code>@username</code>ini, sonli ID raqamini kiriting yoki kanal/guruhdan biror xabarni shu yerga forward qiling:\n\n"
        "<i>Eslatma: Bot avval o'sha kanal/guruhga admin qilib qo'shilgan bo'lishi kerak.</i>"
    )
    if callback.message:
        await safe_edit_text(callback.message, text)
    await callback.answer()


@router.message(ChannelStates.waiting_for_channel)
async def process_manual_channel_input(
    message: Message, state: FSMContext, bot: Bot, session: AsyncSession
) -> None:
    chat_identifier = None
    if message.forward_from_chat and message.forward_from_chat.type in ("channel", "group", "supergroup"):
        chat_identifier = message.forward_from_chat.id
    elif message.text:
        txt = message.text.strip()
        # Support full links: https://t.me/channel, t.me/channel
        if "t.me/" in txt:
            slug = txt.split("t.me/")[-1].strip().split("/")[0].split("?")[0]
            if not slug.startswith("+") and not slug.startswith("joinchat"):
                chat_identifier = f"@{slug}"
        elif txt.startswith("@"):
            chat_identifier = txt
        elif txt.lstrip("-").isdigit():
            chat_identifier = int(txt)

    if not chat_identifier:
        await message.answer(
            "⚠️ <b>Yaroqsiz ma'lumot!</b>\n\n"
            "Iltimos, quyidagilardan birini yuboring:\n"
            "• Kanal username'i (masalan: <code>@kanal_nomi</code> yoki <code>https://t.me/kanal_nomi</code>)\n"
            "• Yoki kanaldan biror postni bu yerga <b>Forward</b> qilib yuboring\n"
            "• Yoki kanalning sonli ID raqamini kiriting (masalan: <code>-1001234567890</code>)"
        )
        return

    try:
        tg_chat = await bot.get_chat(chat_identifier)
    except TelegramBadRequest as e:
        err_lower = str(e).lower()
        if "chat not found" in err_lower or "user not found" in err_lower:
            await message.answer(
                "❌ <b>Kanal topilmadi yoki bot kanalga qo'shilmagan!</b>\n\n"
                "Iltimos, quyidagilarni tekshiring:\n"
                "1. Kanal username'i to'g'ri yozilganmi?\n"
                "2. <b>Eng muhimi:</b> Avval botni o'sha kanalga kirib <b>Administrator</b> qilib tayinlashingiz shart (aks holda Telegram botga kanalni tekshirishga ruxsat bermaydi)!"
            )
            return
        logger.warning("TelegramBadRequest on get_chat: %s", e)
        await message.answer(f"❌ <b>Xatolik:</b> {escape_html(str(e))}")
        return
    except TelegramForbiddenError:
        await message.answer(
            "❌ <b>Bot ushbu kanalga kira olmadi!</b>\n\n"
            "Kanal sozlamalariga kirib, botni <b>Administrator</b> qilib qo'shing."
        )
        return
    except Exception as e:
        logger.error("Error fetching chat %s: %s", chat_identifier, e)
        await message.answer("❌ Kanalni tekshirishda xatolik yuz berdi. Botni kanalga admin qilib qo'shganingizga ishonch hosil qiling.")
        return

    try:
        bot_user = await bot.get_me()
        member = await bot.get_chat_member(chat_id=tg_chat.id, user_id=bot_user.id)
        if member.status not in ("administrator", "creator"):
            await message.answer(
                "❌ <b>Bot ushbu kanalda administrator emas!</b>\n\n"
                "Iltimos, kanal sozlamalariga kiring va botga <b>Administrator</b> huquqini bering, so'ngra qaytadan yuboring."
            )
            return

        existing = await get_required_channel_by_chat_id(session, tg_chat.id)
        if existing:
            await state.clear()
            await message.answer(f"ℹ️ «{escape_html(existing.title)}» kanali allaqachon ro'yxatga olingan.")
            return

        url = f"https://t.me/{tg_chat.username}" if tg_chat.username else tg_chat.invite_link
        if not url:
            try:
                invite = await bot.create_chat_invite_link(chat_id=tg_chat.id, name="A'zolik havolasi")
                url = invite.invite_link
            except Exception as e:
                logger.warning("Could not auto-create invite link: %s", e)
        title = tg_chat.title or "Kanal"

        try:
            await add_or_update_required_channel(session, chat_id=tg_chat.id, title=title, url=url)
        except IntegrityError:
            await session.rollback()
            await message.answer("ℹ️ Ushbu kanal allaqachon ro'yxatga olingan.")
            await state.clear()
            return

        await state.clear()
        res_msg = f"✅ «<b>{escape_html(title)}</b>» kanali muvaffaqiyatli majburiy kanallar safiga qo'shildi!"
        if not url:
            res_msg += "\n\n💡 <i>Eslatma: Kanal yopiq. Foydalanuvchilar o'tishi uchun havola (URL) kiritishni unutmang.</i>"
        await message.answer(res_msg)

    except TelegramBadRequest as e:
        err_lower = str(e).lower()
        if "user not found" in err_lower or "not a member" in err_lower:
            await message.answer(
                "❌ <b>Bot ushbu kanalga hali admin qilib qo'shilmagan!</b>\n\n"
                "Avval kanalingizga kirib, botni <b>Administrator</b> qiling, so'ngra kanalni qayta yuboring."
            )
            return
        await message.answer(f"❌ <b>Xatolik:</b> {escape_html(str(e))}")
    except Exception as e:
        logger.error("Error manually adding channel %s: %s", chat_identifier, e)
        await message.answer("❌ Kanalni tekshirishda xatolik yuz berdi. Qaytadan urinib ko'ring.")

