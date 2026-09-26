"""Admin protected groups management."""

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from gatebot.db.crud import (
    delete_protected_group,
    get_all_protected_groups,
    get_protected_group_by_id,
    set_protected_group_active,
)
from gatebot.keyboards.inline import group_detail_kb, groups_list_kb
from gatebot.utils.html import escape_html

router = Router(name="admin_groups")


@router.callback_query(F.data == "admin_nav:groups")
async def nav_groups(callback: CallbackQuery, session: AsyncSession) -> None:
    groups = await get_all_protected_groups(session)
    text = (
        "🛡 <b>Himoyalangan guruhlar</b>\n\n"
        "Guruh holatini o'zgartirish yoki sozlash uchun uni bosing:"
    )
    if callback.message:
        await callback.message.edit_text(text, reply_markup=groups_list_kb(groups))
    await callback.answer()


@router.callback_query(F.data.startswith("grp_view:"))
async def view_group(callback: CallbackQuery, session: AsyncSession) -> None:
    group_id = int(callback.data.split(":")[1])
    group = await get_protected_group_by_id(session, group_id)
    if not group:
        await callback.answer("Guruh topilmadi", show_alert=True)
        return

    status = "🟢 Faol (so'rovlar tekshiriladi)" if group.is_active else "🔴 Nofaol (o'chirilgan)"
    text = (
        "🛡 <b>Guruh tafsilotlari:</b>\n\n"
        f"• Nomi: <b>{escape_html(group.title)}</b>\n"
        f"• ID: <code>{group.chat_id}</code>\n"
        f"• Holat: {status}\n"
        f"• Qo'shilgan: {group.added_at.strftime('%Y-%m-%d %H:%M')}"
    )
    if callback.message:
        await callback.message.edit_text(text, reply_markup=group_detail_kb(group))
    await callback.answer()


@router.callback_query(F.data.startswith("grp_toggle:"))
async def toggle_group(callback: CallbackQuery, session: AsyncSession) -> None:
    group_id = int(callback.data.split(":")[1])
    group = await get_protected_group_by_id(session, group_id)
    if not group:
        await callback.answer("Guruh topilmadi", show_alert=True)
        return

    new_status = not group.is_active
    await set_protected_group_active(session, group.chat_id, new_status)
    group.is_active = new_status

    status_text = "🟢 Faol holatga o'tkazildi" if new_status else "🔴 Nofaol holatga o'tkazildi"
    await callback.answer(status_text)
    await view_group(callback, session)


@router.callback_query(F.data.startswith("grp_del:"))
async def delete_group_handler(callback: CallbackQuery, session: AsyncSession) -> None:
    group_id = int(callback.data.split(":")[1])
    group = await get_protected_group_by_id(session, group_id)
    if group:
        await delete_protected_group(session, group.chat_id)
    await callback.answer("Guruh o'chirildi", show_alert=True)
    await nav_groups(callback, session)
