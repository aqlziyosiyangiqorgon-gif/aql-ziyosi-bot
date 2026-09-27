
"""Admin managers list and assignment."""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from gatebot.config import Settings
from gatebot.db.crud import add_admin, get_all_admins, remove_admin
from gatebot.keyboards.inline import (
    AdminCb,
    NavCb,
    admin_detail_kb,
    admins_list_kb,
)
from gatebot.texts import ADMIN_ADDED, ADMIN_REMOVED
from gatebot.utils.html import safe_edit_text

router = Router(name="admin_admins")


class AdminStates(StatesGroup):
    waiting_for_admin_id = State()


@router.callback_query(NavCb.filter(F.target == "admins"))
async def nav_admins(
    callback: CallbackQuery, session: AsyncSession, settings: Settings
) -> None:
    admins = await get_all_admins(session)
    text = (
        "👥 <b>Administratorlar ro'yxati</b>\n\n"
        "Yangi admin qo'shish yoki mavjudlarini ko'rish:"
    )
    if callback.message:
        await safe_edit_text(callback.message,
            text, reply_markup=admins_list_kb(admins, settings.ADMIN_IDS)
        )
    await callback.answer()


@router.callback_query(AdminCb.filter(F.action == "add"))
async def start_add_admin(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminStates.waiting_for_admin_id)
    if callback.message:
        await safe_edit_text(callback.message,
            "👤 Yangi administratorning Telegram User ID raqamini kiriting:"
        )
    await callback.answer()


@router.message(AdminStates.waiting_for_admin_id)
async def process_add_admin(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    text = (message.text or "").strip()
    if not text.isdigit() or int(text) == 0:
        await message.answer("⚠️ Yaroqli Telegram ID kiriting (musbat son):")
        return

    tg_id = int(text)
    await add_admin(session, tg_id=tg_id, added_by=message.from_user.id if message.from_user else None)
    await state.clear()
    await message.answer(ADMIN_ADDED.format(tg_id=tg_id))


@router.callback_query(AdminCb.filter(F.action == "view"))
async def view_admin(
    callback: CallbackQuery, callback_data: AdminCb, settings: Settings
) -> None:
    admin_id = callback_data.admin_id
    is_super = admin_id in settings.ADMIN_IDS
    super_badge = " ⭐ (Super Admin)" if is_super else ""
    text = f"👤 Administrator ID: <code>{admin_id}</code>{super_badge}"
    if callback.message:
        await safe_edit_text(callback.message, text, reply_markup=admin_detail_kb(admin_id, is_super))
    await callback.answer()


@router.callback_query(AdminCb.filter(F.action == "del"))
async def delete_admin_handler(
    callback: CallbackQuery, callback_data: AdminCb, session: AsyncSession, settings: Settings
) -> None:
    admin_id = callback_data.admin_id
    if admin_id in settings.ADMIN_IDS:
        await callback.answer("Super adminni o'chirib bo'lmaydi!", show_alert=True)
        return

    await remove_admin(session, admin_id)
    await callback.answer(ADMIN_REMOVED.format(tg_id=admin_id))
    await nav_admins(callback, session, settings)
