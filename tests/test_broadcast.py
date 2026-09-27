"""Broadcast service and admin broadcast flow tests."""

from unittest.mock import AsyncMock, MagicMock
import pytest
from aiogram.exceptions import TelegramForbiddenError
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey
from aiogram.types import CallbackQuery, Chat, Message, User

from gatebot.db.crud import (
    add_or_update_protected_group,
    add_or_update_user,
    get_active_broadcast_users,
    get_broadcast_counts,
)
from gatebot.handlers.admin.broadcast import (
    BroadcastStates,
    cancel_broadcast,
    execute_broadcast,
    process_broadcast_message,
    process_target_selection,
    start_broadcast,
)
from gatebot.keyboards.inline import BroadcastCb, NavCb
from gatebot.services.broadcast import send_broadcast


@pytest.mark.asyncio
async def test_add_or_update_user_and_counts(db_session):
    """Test user creation, update, and broadcast counts."""
    u1 = await add_or_update_user(db_session, tg_id=111, first_name="Ali", username="ali_uz")
    assert u1.tg_id == 111
    assert u1.is_bot_blocked is False

    # Update existing user
    u1_updated = await add_or_update_user(db_session, tg_id=111, first_name="Alisher")
    assert u1_updated.first_name == "Alisher"

    # Add second user
    await add_or_update_user(db_session, tg_id=222, first_name="Vali")

    # Add protected group
    await add_or_update_protected_group(db_session, chat_id=-100999, title="Test Group")

    counts = await get_broadcast_counts(db_session)
    assert counts["users"] == 2
    assert counts["groups"] == 1
    assert counts["total"] == 3


@pytest.mark.asyncio
async def test_send_broadcast_delivery_and_blocked(mock_bot, db_session):
    """Test broadcast dispatching and handling of blocked users."""
    await add_or_update_user(db_session, tg_id=101, first_name="User 1")
    await add_or_update_user(db_session, tg_id=102, first_name="User 2")
    await add_or_update_protected_group(db_session, chat_id=-100555, title="Group 1")

    # User 102 blocked the bot
    async def copy_side_effect(chat_id, from_chat_id, message_id):
        if chat_id == 102:
            raise TelegramForbiddenError(method=MagicMock(), message="Forbidden: bot was blocked by the user")
        return MagicMock()

    mock_bot.copy_message = AsyncMock(side_effect=copy_side_effect)

    stats = await send_broadcast(
        bot=mock_bot,
        session=db_session,
        target_type="all",
        from_chat_id=9999,
        message_id=42,
    )

    assert stats.total == 3
    assert stats.delivered == 2
    assert stats.blocked == 1
    assert stats.failed == 0

    # User 102 should now be marked as blocked
    active_users = await get_active_broadcast_users(db_session)
    active_ids = [u.tg_id for u in active_users]
    assert 101 in active_ids
    assert 102 not in active_ids


@pytest.mark.asyncio
async def test_admin_broadcast_fsm_flow(mock_bot, db_session):
    """Test admin broadcast interaction steps."""
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=123, user_id=123)
    state = FSMContext(storage=storage, key=key)

    # 1. start_broadcast
    cb = AsyncMock(spec=CallbackQuery)
    cb.message = AsyncMock()
    cb.answer = AsyncMock()
    await start_broadcast(cb, state, db_session)
    current_state = await state.get_state()
    assert current_state == BroadcastStates.waiting_for_target.state

    # 2. process_target_selection
    cb_data = BroadcastCb(action="target", target="users")
    await process_target_selection(cb, cb_data, state)
    data = await state.get_data()
    assert data["target"] == "users"
    assert await state.get_state() == BroadcastStates.waiting_for_message.state

    # 3. process_broadcast_message
    msg = AsyncMock(spec=Message)
    msg.chat = Chat(id=123, type="private")
    msg.message_id = 77
    msg.answer = AsyncMock()
    await process_broadcast_message(msg, state)
    data = await state.get_data()
    assert data["message_id"] == 77
    assert await state.get_state() == BroadcastStates.confirm.state

    # 4. execute_broadcast
    mock_bot.copy_message = AsyncMock()
    await execute_broadcast(cb, state, mock_bot, db_session)
    assert await state.get_state() is None

    # 5. cancel_broadcast
    await state.set_state(BroadcastStates.waiting_for_message)
    await cancel_broadcast(cb, state, db_session)
    assert await state.get_state() is None
