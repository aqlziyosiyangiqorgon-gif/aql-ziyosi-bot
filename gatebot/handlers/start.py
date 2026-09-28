"""Start command handler."""

from aiogram import Bot, Router
from aiogram.enums import ChatType
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from gatebot.config import Settings
from gatebot.db.crud import add_or_update_user, is_admin
from gatebot.keyboards.inline import NavCb, SupportCb
from gatebot.texts import PUBLIC_GREETING, WELCOME_ADMIN

router = Router(name="start")


@router.message(CommandStart())
async def handle_start(
    message: Message, session: AsyncSession, settings: Settings, bot: Bot
) -> None:
    """Handle /start command in private chat."""
    if message.chat.type != ChatType.PRIVATE or not message.from_user:
        return

    # Track user for broadcasts
    await add_or_update_user(
        session,
        tg_id=message.from_user.id,
        first_name=message.from_user.first_name,
        username=message.from_user.username,
    )

    bot_user = await bot.get_me()
    bot_username = bot_user.username or ""
    add_group_url = (
        f"https://t.me/{bot_username}?startgroup=true&admin=delete_messages+invite_users+restrict_members"
    )
    add_channel_url = (
        f"https://t.me/{bot_username}?startchannel=true&admin=post_messages+edit_messages+delete_messages+invite_users"
    )

    user_is_adm = await is_admin(session, message.from_user.id, settings.ADMIN_IDS)
    if user_is_adm:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📢 Mening kanalim (Admin qilish)", url=add_channel_url)],
                [InlineKeyboardButton(text="👥 Guruhimga qo'shish (Admin qilish)", url=add_group_url)],
                [InlineKeyboardButton(text="⚙️ Administrator paneli", callback_data=NavCb(target="main").pack())],
                [InlineKeyboardButton(text="💬 Qo'llab-quvvatlash", callback_data=SupportCb(action="write").pack())],
            ]
        )
        await message.answer(WELCOME_ADMIN, reply_markup=kb)
    else:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="➕ Guruhimga qo'shish (Admin qilish)", url=add_group_url)],
                [InlineKeyboardButton(text="💬 Qo'llab-quvvatlash / Bog'lanish", callback_data=SupportCb(action="write").pack())],
            ]
        )
        await message.answer(PUBLIC_GREETING, reply_markup=kb)
