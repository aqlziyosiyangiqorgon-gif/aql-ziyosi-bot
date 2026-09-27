"""Tests for user support ticketing and admin reply."""

from unittest.mock import AsyncMock
import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey
from aiogram.types import CallbackQuery, Chat, Message, User

from gatebot.handlers.support import (
    SupportStates,
    cancel_support_action,
    process_admin_reply,
    process_user_support_message,
    start_admin_reply,
    start_user_support,
)
from gatebot.keyboards.inline import SupportCb


@pytest.mark.asyncio
async def test_user_support_flow(mock_bot, test_settings):
    """Test user initiating support, forwarding to admins, and admin reply."""
    storage = MemoryStorage()
    key_user = StorageKey(bot_id=1, chat_id=123, user_id=123)
    state_user = FSMContext(storage=storage, key=key_user)

    # 1. start_user_support
    cb = AsyncMock(spec=CallbackQuery)
    cb.message = AsyncMock()
    cb.answer = AsyncMock()
    await start_user_support(cb, state_user)
    assert await state_user.get_state() == SupportStates.waiting_for_user_message.state

    # 2. process_user_support_message
    msg = AsyncMock(spec=Message)
    msg.from_user = User(id=123, is_bot=False, first_name="Davron", username="davron_dev")
    msg.chat = Chat(id=123, type="private")
    msg.message_id = 55
    msg.answer = AsyncMock()

    await process_user_support_message(msg, state_user, mock_bot, test_settings)

    # Message cleared
    assert await state_user.get_state() is None

    # Bot forwarded to all test admin IDs
    assert mock_bot.send_message.call_count >= 1
    assert mock_bot.copy_message.call_count >= 1
    call_args = mock_bot.send_message.call_args[1]
    assert call_args["chat_id"] in test_settings.ADMIN_IDS
    assert "Yangi murojaat" in call_args["text"]
    assert "Davron" in call_args["text"]


@pytest.mark.asyncio
async def test_admin_reply_flow(mock_bot):
    """Test admin replying to a support ticket."""
    storage = MemoryStorage()
    key_admin = StorageKey(bot_id=1, chat_id=999, user_id=999)
    state_admin = FSMContext(storage=storage, key=key_admin)

    # 1. start_admin_reply
    cb = AsyncMock(spec=CallbackQuery)
    cb.message = AsyncMock()
    cb.answer = AsyncMock()
    cb_data = SupportCb(action="reply", user_id=123)

    await start_admin_reply(cb, cb_data, state_admin)
    data = await state_admin.get_data()
    assert data["target_user_id"] == 123
    assert await state_admin.get_state() == SupportStates.waiting_for_admin_reply.state

    # 2. process_admin_reply
    msg = AsyncMock(spec=Message)
    msg.chat = Chat(id=999, type="private")
    msg.message_id = 99
    msg.answer = AsyncMock()

    await process_admin_reply(msg, state_admin, mock_bot)

    # User received admin reply header + copy_message
    assert mock_bot.send_message.called
    assert mock_bot.copy_message.called
    assert mock_bot.send_message.call_args[1]["chat_id"] == 123
    assert "Administrator javobi" in mock_bot.send_message.call_args[1]["text"]
    assert await state_admin.get_state() is None


@pytest.mark.asyncio
async def test_cancel_support(mock_bot):
    """Test canceling support FSM."""
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=123, user_id=123)
    state = FSMContext(storage=storage, key=key)
    await state.set_state(SupportStates.waiting_for_user_message)

    cb = AsyncMock(spec=CallbackQuery)
    cb.message = AsyncMock()
    cb.answer = AsyncMock()

    await cancel_support_action(cb, state)
    assert await state.get_state() is None
