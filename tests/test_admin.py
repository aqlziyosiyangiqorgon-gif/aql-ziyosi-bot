"""Admin middleware and panel tests."""

from unittest.mock import AsyncMock

import pytest
from aiogram.enums import ChatType
from aiogram.types import Chat, User

from gatebot.db.crud import add_admin
from gatebot.middlewares.admin_only import AdminOnlyMiddleware
from gatebot.texts import NOT_ADMIN


@pytest.mark.asyncio
async def test_admin_only_middleware(db_session, test_settings):
    """AdminOnlyMiddleware blocks non-admins and allows super/DB admins."""
    middleware = AdminOnlyMiddleware()
    handler = AsyncMock()

    # 1. Non-admin in private chat
    user_non_admin = User(id=99999, is_bot=False, first_name="Stranger")
    msg_non_admin = AsyncMock()
    msg_non_admin.chat = Chat(id=99999, type=ChatType.PRIVATE)
    msg_non_admin.from_user = user_non_admin
    msg_non_admin.answer = AsyncMock()

    data = {
        "event_from_user": user_non_admin,
        "session": db_session,
        "settings": test_settings,
    }

    res = await middleware(handler, msg_non_admin, data)
    assert res is None
    handler.assert_not_called()
    msg_non_admin.answer.assert_called_once_with(NOT_ADMIN)

    # 2. Super admin
    super_admin_user = User(id=test_settings.ADMIN_IDS[0], is_bot=False, first_name="Super")
    msg_super = AsyncMock()
    msg_super.chat = Chat(id=test_settings.ADMIN_IDS[0], type=ChatType.PRIVATE)
    msg_super.answer = AsyncMock()
    data["event_from_user"] = super_admin_user

    handler.reset_mock()
    handler.return_value = "ok"
    res = await middleware(handler, msg_super, data)
    assert res == "ok"
    handler.assert_called_once()

    # 3. DB Admin
    await add_admin(db_session, tg_id=888777)
    db_admin_user = User(id=888777, is_bot=False, first_name="DbAdmin")
    msg_db_admin = AsyncMock()
    msg_db_admin.chat = Chat(id=888777, type=ChatType.PRIVATE)
    msg_db_admin.answer = AsyncMock()
    data["event_from_user"] = db_admin_user

    handler.reset_mock()
    handler.return_value = "ok"
    res = await middleware(handler, msg_db_admin, data)
    assert res == "ok"
    handler.assert_called_once()
