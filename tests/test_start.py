"""Unit tests for start command handler."""

from unittest.mock import AsyncMock
import pytest
from aiogram.types import Chat, Message, User

from gatebot.handlers.start import handle_start
from gatebot.texts import PUBLIC_GREETING, WELCOME_ADMIN


@pytest.mark.asyncio
async def test_handle_start_public_user(db_session, test_settings, mock_bot):
    """Test /start for non-admin user creates user and shows 1-tap add group button."""
    mock_bot_user = AsyncMock()
    mock_bot_user.username = "test_gate_bot"
    mock_bot.get_me.return_value = mock_bot_user

    msg = AsyncMock(spec=Message)
    msg.chat = Chat(id=99999, type="private")
    msg.from_user = User(id=99999, is_bot=False, first_name="Ali", username="ali_user")
    msg.answer = AsyncMock()

    await handle_start(msg, db_session, test_settings, mock_bot)

    msg.answer.assert_called_once()
    args, kwargs = msg.answer.call_args
    assert args[0] == PUBLIC_GREETING
    reply_markup = kwargs["reply_markup"]
    assert len(reply_markup.inline_keyboard) == 2
    assert "startgroup=true" in reply_markup.inline_keyboard[0][0].url
    assert "test_gate_bot" in reply_markup.inline_keyboard[0][0].url


@pytest.mark.asyncio
async def test_handle_start_admin_user(db_session, test_settings, mock_bot):
    """Test /start for super admin shows admin panel and 1-tap group/channel links."""
    mock_bot_user = AsyncMock()
    mock_bot_user.username = "test_gate_bot"
    mock_bot.get_me.return_value = mock_bot_user

    msg = AsyncMock(spec=Message)
    msg.chat = Chat(id=111222333, type="private")
    msg.from_user = User(id=111222333, is_bot=False, first_name="Admin", username="admin_user")
    msg.answer = AsyncMock()

    await handle_start(msg, db_session, test_settings, mock_bot)

    msg.answer.assert_called_once()
    args, kwargs = msg.answer.call_args
    assert args[0] == WELCOME_ADMIN
    reply_markup = kwargs["reply_markup"]
    assert len(reply_markup.inline_keyboard) == 4
    assert reply_markup.inline_keyboard[0][0].callback_data.startswith("n:main")
    assert "startgroup=true" in reply_markup.inline_keyboard[1][0].url
    assert "startchannel=true" in reply_markup.inline_keyboard[2][0].url