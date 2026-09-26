"""Start command handler."""

from aiogram import Router
from aiogram.enums import ChatType
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from gatebot.config import Settings
from gatebot.db.crud import is_admin
from gatebot.texts import PUBLIC_GREETING, WELCOME_ADMIN

router = Router(name="start")


@router.message(CommandStart())
async def handle_start(
    message: Message, session: AsyncSession, settings: Settings
) -> None:
    """Handle /start command in private chat."""
    if message.chat.type != ChatType.PRIVATE or not message.from_user:
        return

    user_is_adm = await is_admin(session, message.from_user.id, settings.ADMIN_IDS)
    if user_is_adm:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⚙️ Admin panel", callback_data="admin_nav:main")]
            ]
        )
        await message.answer(WELCOME_ADMIN, reply_markup=kb)
    else:
        await message.answer(PUBLIC_GREETING)
