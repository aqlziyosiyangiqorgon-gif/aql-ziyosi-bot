"""Admin middleware, panel actions, statistics, and duplicate checks."""

from unittest.mock import AsyncMock

import pytest
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.types import (
    CallbackQuery,
    Chat,
    ChatMemberAdministrator,
    Message,
    User,
)

from gatebot.db.crud import (
    add_admin,
    add_or_update_protected_group,
    add_or_update_required_channel,
    get_join_stats,
    get_protected_group_by_chat_id,
    get_required_channel_by_chat_id,
    log_join_event,
    update_channel_sort_order,
)
from gatebot.handlers.admin.admins import delete_admin_handler
from gatebot.handlers.admin.channels import process_manual_channel_input
from gatebot.handlers.admin.groups import (
    check_group_rights,
    process_manual_group_input,
)
from gatebot.keyboards.inline import AdminCb, GroupCb
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


@pytest.mark.asyncio
async def test_super_admin_cannot_be_deleted(db_session, test_settings):
    """Verify super admins cannot be deleted via admin panel."""
    super_id = test_settings.ADMIN_IDS[0]
    cb = AsyncMock(spec=CallbackQuery)
    cb.answer = AsyncMock()
    cb_data = AdminCb(action="del", admin_id=super_id)

    await delete_admin_handler(cb, cb_data, db_session, test_settings)
    cb.answer.assert_called_once_with("Super adminni o'chirib bo'lmaydi!", show_alert=True)


@pytest.mark.asyncio
async def test_group_rights_check_button(mock_bot, db_session):
    """Verify '🔗 Tekshirish' button tests bot rights in group."""
    group = await add_or_update_protected_group(db_session, chat_id=-100555, title="Checked Group")
    bot_user = User(id=9999, is_bot=True, first_name="GateBot")
    mock_bot.get_me.return_value = bot_user

    # Case 1: has invite rights
    mock_bot.get_chat_member.return_value = ChatMemberAdministrator.model_construct(
        status=ChatMemberStatus.ADMINISTRATOR,
        user=bot_user,
        can_invite_users=True,
    )
    cb = AsyncMock(spec=CallbackQuery)
    cb.answer = AsyncMock()
    cb_data = GroupCb(action="check", group_id=group.id)

    await check_group_rights(cb, cb_data, mock_bot, db_session)
    cb.answer.assert_called_with("✅ Barcha huquqlar joyida! Bot so'rovlarni boshqara oladi.", show_alert=True)


@pytest.mark.asyncio
async def test_manual_group_add_and_duplicate(mock_bot, db_session):
    """Manual add adds group; duplicate shows friendly message."""
    bot_user = User(id=9999, is_bot=True, first_name="GateBot")
    mock_bot.get_me.return_value = bot_user
    mock_bot.get_chat.return_value = Chat(id=-100777, type=ChatType.SUPERGROUP, title="Manual Group")
    mock_bot.get_chat_member.return_value = ChatMemberAdministrator.model_construct(
        status=ChatMemberStatus.ADMINISTRATOR,
        user=bot_user,
        can_invite_users=True,
    )

    state = AsyncMock()
    msg = AsyncMock(spec=Message)
    msg.forward_from_chat = None
    msg.text = "-100777"
    msg.answer = AsyncMock()

    # 1. First addition -> success
    await process_manual_group_input(msg, state, mock_bot, db_session)
    g = await get_protected_group_by_chat_id(db_session, -100777)
    assert g is not None
    assert g.title == "Manual Group"
    assert "muvaffaqiyatli" in msg.answer.call_args[0][0]

    # 2. Second addition -> duplicate handled gracefully
    msg.answer.reset_mock()
    await process_manual_group_input(msg, state, mock_bot, db_session)
    assert "allaqachon" in msg.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_manual_channel_add_and_duplicate(mock_bot, db_session):
    """Manual add adds channel; duplicate shows friendly message."""
    bot_user = User(id=9999, is_bot=True, first_name="GateBot")
    mock_bot.get_me.return_value = bot_user
    mock_bot.get_chat.return_value = Chat(
        id=-100888,
        type=ChatType.CHANNEL,
        title="Manual Channel",
        username="manual_chan",
    )
    mock_bot.get_chat_member.return_value = ChatMemberAdministrator.model_construct(
        status=ChatMemberStatus.ADMINISTRATOR,
        user=bot_user,
    )

    state = AsyncMock()
    msg = AsyncMock(spec=Message)
    msg.forward_from_chat = None
    msg.text = "@manual_chan"
    msg.answer = AsyncMock()

    # 1. First addition -> success
    await process_manual_channel_input(msg, state, mock_bot, db_session)
    ch = await get_required_channel_by_chat_id(db_session, -100888)
    assert ch is not None
    assert ch.title == "Manual Channel"
    assert "muvaffaqiyatli" in msg.answer.call_args[0][0]

    # 2. Second addition -> duplicate handled gracefully
    msg.answer.reset_mock()
    await process_manual_channel_input(msg, state, mock_bot, db_session)
    assert "allaqachon" in msg.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_statistics_and_channel_reorder(db_session):
    """Verify join statistics and channel reordering calculations."""
    g = await add_or_update_protected_group(db_session, chat_id=-1001, title="Stat Group")
    ch = await add_or_update_required_channel(db_session, chat_id=-2001, title="Sort Channel")
    assert ch.sort_order == 0

    # Reorder
    await update_channel_sort_order(db_session, ch.id, delta=5)
    ch_updated = await get_required_channel_by_chat_id(db_session, -2001)
    assert ch_updated.sort_order == 5

    # Log some events
    await log_join_event(db_session, group_id=g.id, user_id=1, user_name="A", status="approved")
    await log_join_event(db_session, group_id=g.id, user_id=2, user_name="B", status="declined", missing_channels="Ch1, Ch2")
    await log_join_event(db_session, group_id=g.id, user_id=3, user_name="C", status="declined", missing_channels="Ch1")

    stats = await get_join_stats(db_session)
    assert stats["total_approved"] == 1
    assert stats["total_declined"] == 2
    assert stats["approved_7d"] == 1
    assert stats["declined_7d"] == 2

    # Top missing
    top = dict(stats["top_missing"])
    assert top["Ch1"] == 2
    assert top["Ch2"] == 1
