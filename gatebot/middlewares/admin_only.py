"""Admin authorization middleware."""

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.enums import ChatType
from aiogram.types import CallbackQuery, TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

from gatebot.config import Settings
from gatebot.db.crud import is_admin
from gatebot.texts import NOT_ADMIN


class AdminOnlyMiddleware(BaseMiddleware):
    """
    Enforces admin access for routes.
    Allows users listed in config.ADMIN_IDS or the `admins` DB table in private chat.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if not user:
            return None

        # Check private chat only
        chat = getattr(event, "chat", None)
        if chat and chat.type != ChatType.PRIVATE:
            return None

        session: AsyncSession = data.get("session")
        settings: Settings = data.get("settings")

        if not session or not settings:
            return None

        has_access = await is_admin(session, user.id, settings.ADMIN_IDS)
        if not has_access:
            if isinstance(event, CallbackQuery):
                await event.answer(NOT_ADMIN, show_alert=True)
            elif hasattr(event, "answer"):
                await event.answer(NOT_ADMIN)
            return None

        return await handler(event, data)
