"""Inline keyboards and aiogram CallbackData factories."""

from collections.abc import Sequence

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from gatebot.db.models import Admin, ProtectedGroup, RequiredChannel


# --- CallbackData Factories (guaranteed <= 64 bytes) ---
class NavCb(CallbackData, prefix="n"):
    target: str  # "main", "groups", "channels", "admins", "stats", "backup"


class GroupCb(CallbackData, prefix="g"):
    action: str  # "view", "toggle", "check", "del", "add"
    group_id: int = 0


class ChannelCb(CallbackData, prefix="c"):
    action: str  # "view", "toggle", "url", "up", "down", "del", "add"
    channel_id: int = 0


class AdminCb(CallbackData, prefix="a"):
    action: str  # "view", "del", "add"
    admin_id: int = 0


# --- Detection confirmation keyboards ---
def group_confirm_kb(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ha, himoyalash", callback_data=f"group_add:{chat_id}"),
                InlineKeyboardButton(text="❌ Yo'q", callback_data=f"group_reject:{chat_id}"),
            ]
        ]
    )


def channel_confirm_kb(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ha, majburiy qilish", callback_data=f"chan_add:{chat_id}"),
                InlineKeyboardButton(text="❌ Yo'q", callback_data=f"chan_reject:{chat_id}"),
            ]
        ]
    )


def missing_channels_kb(channels: Sequence[RequiredChannel]) -> InlineKeyboardMarkup | None:
    rows: list[list[InlineKeyboardButton]] = []
    for ch in channels:
        if ch.url:
            rows.append([InlineKeyboardButton(text=f"👉 {ch.title}", url=ch.url)])
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


# --- Admin Dashboard Keyboards ---
def admin_main_menu_kb(
    groups_count: int, channels_count: int, admins_count: int
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"👥 Guruhlar ({groups_count})",
                    callback_data=NavCb(target="groups").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"📢 Kanallar ({channels_count})",
                    callback_data=NavCb(target="channels").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"👥 Adminlar ({admins_count})",
                    callback_data=NavCb(target="admins").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="📊 Statistika",
                    callback_data=NavCb(target="stats").pack(),
                ),
                InlineKeyboardButton(
                    text="💾 Zaxira nusxa",
                    callback_data=NavCb(target="backup").pack(),
                ),
            ],
        ]
    )


# --- Groups Keyboards ---
def groups_list_kb(groups: Sequence[ProtectedGroup]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for g in groups:
        status_icon = "🟢" if g.is_active else "🔴"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{status_icon} {g.title}",
                    callback_data=GroupCb(action="view", group_id=g.id).pack(),
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="➕ Qo'lda guruh qo'shish",
                callback_data=GroupCb(action="add", group_id=0).pack(),
            )
        ]
    )
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data=NavCb(target="main").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def group_detail_kb(group: ProtectedGroup) -> InlineKeyboardMarkup:
    toggle_text = "🗑 Olib tashlash (nofaol qilish)" if group.is_active else "♻️ Qayta yoqish"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔗 Tekshirish",
                    callback_data=GroupCb(action="check", group_id=group.id).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text=toggle_text,
                    callback_data=GroupCb(action="toggle", group_id=group.id).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="🗑 Butunlay o'chirish",
                    callback_data=GroupCb(action="del", group_id=group.id).pack(),
                )
            ],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data=NavCb(target="groups").pack())],
        ]
    )


# --- Channels Keyboards ---
def channels_list_kb(channels: Sequence[RequiredChannel]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for ch in channels:
        status_icon = "🟢" if ch.is_active else "🔴"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{status_icon} [{ch.sort_order}] {ch.title}",
                    callback_data=ChannelCb(action="view", channel_id=ch.id).pack(),
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="➕ Qo'lda kanal qo'shish",
                callback_data=ChannelCb(action="add", channel_id=0).pack(),
            )
        ]
    )
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data=NavCb(target="main").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def channel_detail_kb(channel: RequiredChannel) -> InlineKeyboardMarkup:
    toggle_text = "🗑 Olib tashlash (nofaol qilish)" if channel.is_active else "♻️ Qayta yoqish"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=toggle_text,
                    callback_data=ChannelCb(action="toggle", channel_id=channel.id).pack(),
                ),
                InlineKeyboardButton(
                    text="🔗 Havola",
                    callback_data=ChannelCb(action="url", channel_id=channel.id).pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⬆️ Tartib (+1)",
                    callback_data=ChannelCb(action="up", channel_id=channel.id).pack(),
                ),
                InlineKeyboardButton(
                    text="⬇️ Tartib (-1)",
                    callback_data=ChannelCb(action="down", channel_id=channel.id).pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🗑 Butunlay o'chirish",
                    callback_data=ChannelCb(action="del", channel_id=channel.id).pack(),
                )
            ],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data=NavCb(target="channels").pack())],
        ]
    )


# --- Admins Keyboards ---
def admins_list_kb(admins: Sequence[Admin], super_admin_ids: list[int]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for a in admins:
        is_super = a.tg_id in super_admin_ids
        badge = " ⭐ (Super)" if is_super else ""
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"👤 ID: {a.tg_id}{badge}",
                    callback_data=AdminCb(action="view", admin_id=a.tg_id).pack(),
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="➕ Yangi admin qo'shish",
                callback_data=AdminCb(action="add", admin_id=0).pack(),
            )
        ]
    )
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data=NavCb(target="main").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_detail_kb(admin_id: int, is_super: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if not is_super:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🗑 Adminlikdan olish",
                    callback_data=AdminCb(action="del", admin_id=admin_id).pack(),
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data=NavCb(target="admins").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# --- Statistics and Backup Keyboards ---
def stats_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Yangilash",
                    callback_data=NavCb(target="stats").pack(),
                ),
                InlineKeyboardButton(
                    text="⬅️ Bosh menyu",
                    callback_data=NavCb(target="main").pack(),
                ),
            ]
        ]
    )


def backup_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💾 Hozir zaxira olish",
                    callback_data=NavCb(target="backup_now").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Bosh menyu",
                    callback_data=NavCb(target="main").pack(),
                )
            ],
        ]
    )
