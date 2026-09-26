"""Admin dashboard overview, statistics, and backup."""

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from gatebot.config import Settings
from gatebot.db.crud import (
    get_all_admins,
    get_all_protected_groups,
    get_all_required_channels,
    get_join_stats,
)
from gatebot.keyboards.inline import (
    NavCb,
    admin_main_menu_kb,
    backup_kb,
    stats_kb,
)
from gatebot.services.backup import perform_backup
from gatebot.utils.html import escape_html

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
    await message.answer("⚙️ <b>Administrator paneli</b>\n\nKerakli bo'limni tanlang:", reply_markup=kb)


@router.callback_query(NavCb.filter())
async def handle_navigation(
    callback: CallbackQuery,
    callback_data: NavCb,
    bot: Bot,
    session: AsyncSession,
    settings: Settings,
) -> None:
    """Central router for top-level admin menu navigation."""
    target = callback_data.target

    if target == "main":
        groups = await get_all_protected_groups(session)
        channels = await get_all_required_channels(session)
        admins = await get_all_admins(session)
        kb = admin_main_menu_kb(
            groups_count=len(groups),
            channels_count=len(channels),
            admins_count=len(admins),
        )
        if callback.message:
            await callback.message.edit_text("⚙️ <b>Administrator paneli</b>\n\nKerakli bo'limni tanlang:", reply_markup=kb)

    elif target == "stats":
        stats = await get_join_stats(session)
        group_lines = []
        for g in stats["groups"]:
            status_dot = "🟢" if g["is_active"] else "🔴"
            group_lines.append(
                f"• {status_dot} <b>{escape_html(g['title'])}</b>: "
                f"✅ {g['approved']} ta | ❌ {g['declined']} ta"
            )
        group_section = "\n".join(group_lines) if group_lines else "<i>Guruhlar mavjud emas</i>"

        missing_lines = []
        for ch_title, count in stats["top_missing"]:
            missing_lines.append(f"• <b>{escape_html(ch_title)}</b>: {count} marta")
        missing_section = "\n".join(missing_lines) if missing_lines else "<i>Mavjud emas</i>"

        text = (
            "📊 <b>A'zolik so'rovlari statistikasi</b>\n\n"
            f"<b>Umumiy ko'rsatkichlar (all-time):</b>\n"
            f"✅ Tasdiqlangan: <b>{stats['total_approved']}</b>\n"
            f"❌ Rad etilgan: <b>{stats['total_declined']}</b>\n\n"
            f"<b>Oxirgi 7 kun:</b>\n"
            f"✅ Tasdiqlangan: <b>{stats['approved_7d']}</b>\n"
            f"❌ Rad etilgan: <b>{stats['declined_7d']}</b>\n\n"
            f"<b>Guruhlar kesimida:</b>\n{group_section}\n\n"
            f"<b>Eng ko'p yetishmagan kanallar:</b>\n{missing_section}"
        )
        if callback.message:
            await callback.message.edit_text(text, reply_markup=stats_kb())

    elif target == "backup":
        text = (
            "💾 <b>Ma'lumotlar bazasi zaxirasi</b>\n\n"
            "Tizim har kuni soat 03:00 da avtomatik zaxira nusxa oladi.\n"
            "Zaxira nusxa olishni hoziroq ishga tushirishingiz mumkin:"
        )
        if callback.message:
            await callback.message.edit_text(text, reply_markup=backup_kb())

    elif target == "backup_now":
        if callback.message:
            await callback.message.edit_text("⏳ Zaxira nusxa olinmoqda, iltimos kuting...")
        success = await perform_backup(bot, settings)
        status_msg = (
            "✅ <b>Zaxira nusxa muvaffaqiyatli olindi va yuborildi!</b>"
            if success
            else "❌ <b>Zaxira nusxa olishda xatolik yuz berdi.</b>"
        )
        if callback.message:
            await callback.message.edit_text(status_msg, reply_markup=backup_kb())

    await callback.answer()
