"""Admin dashboard overview."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from gatebot.db.crud import (
    get_all_admins,
    get_all_protected_groups,
    get_all_required_channels,
)
from gatebot.keyboards.inline import admin_main_menu_kb
from gatebot.texts import ADMIN_MENU_TITLE

router = Router(name="admin_menu")


@router.message(Command("admin"))
async def cmd_admin(message: Message, session: AsyncSession) -> None:
    """Show admin panel dashboard."""
    groups = await get_all_protected_groups(session)
    channels = await get_all_required_channels(session)
    admins = await get_all_admins(session)

    kb = admin_main_menu_kb(
        groups_count=len(groups),
        channels_count=len(channels),
        admins_count=len(admins),
    )
    await message.answer(ADMIN_MENU_TITLE, reply_markup=kb)


@router.callback_query(F.data == "admin_nav:main")
async def nav_main_menu(callback: CallbackQuery, session: AsyncSession) -> None:
    """Return to admin panel dashboard."""
    groups = await get_all_protected_groups(session)
    channels = await get_all_required_channels(session)
    admins = await get_all_admins(session)

    kb = admin_main_menu_kb(
        groups_count=len(groups),
        channels_count=len(channels),
        admins_count=len(admins),
    )
    await callback.message.edit_text(ADMIN_MENU_TITLE, reply_markup=kb)
    await callback.answer()
