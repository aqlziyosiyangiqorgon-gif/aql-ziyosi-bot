"""Inline keyboards for menus, confirmations, and missing channels."""

from collections.abc import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from gatebot.db.models import Admin, ProtectedGroup, RequiredChannel
from gatebot.texts import (
    ADMIN_BTN_ADMINS,
    ADMIN_BTN_CHANNELS,
    ADMIN_BTN_GROUPS,
    BTN_BACK,
    BTN_CONFIRM_PROTECT,
    BTN_CONFIRM_REQUIRED,
    BTN_REJECT_PROTECT,
    BTN_REJECT_REQUIRED,
)


def group_confirm_kb(chat_id: int) -> InlineKeyboardMarkup:
    """Confirmation keyboard when bot is added to a group."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=BTN_CONFIRM_PROTECT, callback_data=f"group_add:{chat_id}"),
                InlineKeyboardButton(text=BTN_REJECT_PROTECT, callback_data=f"group_reject:{chat_id}"),
            ]
        ]
    )


def channel_confirm_kb(chat_id: int) -> InlineKeyboardMarkup:
    """Confirmation keyboard when bot is added to a channel."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=BTN_CONFIRM_REQUIRED, callback_data=f"chan_add:{chat_id}"),
                InlineKeyboardButton(text=BTN_REJECT_REQUIRED, callback_data=f"chan_reject:{chat_id}"),
            ]
        ]
    )


def missing_channels_kb(channels: Sequence[RequiredChannel]) -> InlineKeyboardMarkup | None:
    """Build inline buttons for missing channels having invite URLs."""
    rows: list[list[InlineKeyboardButton]] = []
    for ch in channels:
        if ch.url:
            rows.append([InlineKeyboardButton(text=f"👉 {ch.title}", url=ch.url)])
    if not rows:
        return None
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_main_menu_kb(
    groups_count: int, channels_count: int, admins_count: int
) -> InlineKeyboardMarkup:
    """Main admin dashboard menu."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=ADMIN_BTN_GROUPS.format(count=groups_count),
                    callback_data="admin_nav:groups",
                )
            ],
            [
                InlineKeyboardButton(
                    text=ADMIN_BTN_CHANNELS.format(count=channels_count),
                    callback_data="admin_nav:channels",
                )
            ],
            [
                InlineKeyboardButton(
                    text=ADMIN_BTN_ADMINS.format(count=admins_count),
                    callback_data="admin_nav:admins",
                )
            ],
        ]
    )


def groups_list_kb(groups: Sequence[ProtectedGroup]) -> InlineKeyboardMarkup:
    """List of protected groups with status toggles."""
    rows: list[list[InlineKeyboardButton]] = []
    for g in groups:
        status_icon = "🟢" if g.is_active else "🔴"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{status_icon} {g.title}",
                    callback_data=f"grp_view:{g.id}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text=BTN_BACK, callback_data="admin_nav:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def group_detail_kb(group: ProtectedGroup) -> InlineKeyboardMarkup:
    """Actions for a single protected group."""
    toggle_text = "🔴 O'chirish (nofaol qilish)" if group.is_active else "🟢 Yoqish (faol qilish)"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=toggle_text, callback_data=f"grp_toggle:{group.id}")],
            [InlineKeyboardButton(text="🗑 Butunlay o'chirish", callback_data=f"grp_del:{group.id}")],
            [InlineKeyboardButton(text=BTN_BACK, callback_data="admin_nav:groups")],
        ]
    )


def channels_list_kb(channels: Sequence[RequiredChannel]) -> InlineKeyboardMarkup:
    """List of required channels with status toggles."""
    rows: list[list[InlineKeyboardButton]] = []
    for ch in channels:
        status_icon = "🟢" if ch.is_active else "🔴"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{status_icon} {ch.title}",
                    callback_data=f"chn_view:{ch.id}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text=BTN_BACK, callback_data="admin_nav:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def channel_detail_kb(channel: RequiredChannel) -> InlineKeyboardMarkup:
    """Actions for a single required channel."""
    toggle_text = "🔴 O'chirish (nofaol qilish)" if channel.is_active else "🟢 Yoqish (faol qilish)"
    rows = [
        [InlineKeyboardButton(text=toggle_text, callback_data=f"chn_toggle:{channel.id}")],
        [InlineKeyboardButton(text="🔗 Havolani o'zgartirish", callback_data=f"chn_url:{channel.id}")],
        [InlineKeyboardButton(text="🗑 Butunlay o'chirish", callback_data=f"chn_del:{channel.id}")],
        [InlineKeyboardButton(text=BTN_BACK, callback_data="admin_nav:channels")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admins_list_kb(admins: Sequence[Admin], super_admin_ids: list[int]) -> InlineKeyboardMarkup:
    """List of administrators with remove option."""
    rows: list[list[InlineKeyboardButton]] = []
    for a in admins:
        is_super = a.tg_id in super_admin_ids
        badge = " ⭐ (Super)" if is_super else ""
        btn_text = f"👤 ID: {a.tg_id}{badge}"
        rows.append(
            [
                InlineKeyboardButton(
                    text=btn_text,
                    callback_data=f"adm_view:{a.tg_id}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="➕ Yangi admin qo'shish", callback_data="adm_add")])
    rows.append([InlineKeyboardButton(text=BTN_BACK, callback_data="admin_nav:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_detail_kb(admin_id: int, is_super: bool) -> InlineKeyboardMarkup:
    """Detail actions for an administrator."""
    rows: list[list[InlineKeyboardButton]] = []
    if not is_super:
        rows.append([InlineKeyboardButton(text="🗑 Adminlikdan olish", callback_data=f"adm_del:{admin_id}")])
    rows.append([InlineKeyboardButton(text=BTN_BACK, callback_data="admin_nav:admins")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
