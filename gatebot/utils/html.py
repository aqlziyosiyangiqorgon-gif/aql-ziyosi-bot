"""HTML escaping and safe Telegram UI utilities."""

import html

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, Message


def escape_html(text: str | None) -> str:
    """Safely escapes text for Telegram HTML parse mode."""
    if not text:
        return ""
    return html.escape(str(text), quote=True)


async def safe_edit_text(
    message: Message | None,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Edits message safely, suppressing Telegram 'message is not modified' error."""
    if not message:
        return
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            return
        raise
