"""Chat join request handler integration tests."""

import pytest
from aiogram.enums import ChatType
from aiogram.types import Chat, ChatJoinRequest, ChatMemberLeft, ChatMemberMember, User
from sqlalchemy import select

from gatebot.db.crud import (
    add_or_update_protected_group,
    add_or_update_required_channel,
)
from gatebot.db.models import JoinEvent
from gatebot.handlers.join_requests import process_chat_join_request
from gatebot.services.notify import clear_alert_history
from gatebot.services.subscription import clear_cache


@pytest.fixture(autouse=True)
def reset_state():
    clear_cache()
    clear_alert_history()


def make_request(chat_id: int, chat_title: str, user_id: int, user_name: str) -> ChatJoinRequest:
    chat = Chat(id=chat_id, type=ChatType.SUPERGROUP, title=chat_title)
    user = User(id=user_id, is_bot=False, first_name=user_name)
    return ChatJoinRequest(
        chat=chat,
        from_user=user,
        user_chat_id=user_id,
        date=1700000000,
    )


@pytest.mark.asyncio
async def test_unmanaged_group_ignored(mock_bot, db_session, test_settings):
    """Join request for unmanaged group -> bot does nothing."""
    req = make_request(chat_id=-100999, chat_title="Unmanaged", user_id=555, user_name="Ali")
    await process_chat_join_request(req, mock_bot, db_session, test_settings)

    mock_bot.approve_chat_join_request.assert_not_called()
    mock_bot.decline_chat_join_request.assert_not_called()
    mock_bot.send_message.assert_not_called()

    # Verify no log entry
    events = (await db_session.execute(select(JoinEvent))).scalars().all()
    assert len(events) == 0


@pytest.mark.asyncio
async def test_managed_group_approved(mock_bot, db_session, test_settings):
    """User member of all required channels -> approved, DM sent, logged."""
    group = await add_or_update_protected_group(db_session, chat_id=-100111, title="VIP Group")
    await add_or_update_required_channel(
        db_session, chat_id=-100222, title="Main Channel", url="https://t.me/main"
    )

    u = User(id=777, is_bot=False, first_name="Jasur")
    mock_bot.get_chat_member.return_value = ChatMemberMember.model_construct(
        status="member", user=u
    )

    req = make_request(chat_id=-100111, chat_title="VIP Group", user_id=777, user_name="Jasur")
    await process_chat_join_request(req, mock_bot, db_session, test_settings)

    mock_bot.approve_chat_join_request.assert_called_once_with(chat_id=-100111, user_id=777)
    mock_bot.decline_chat_join_request.assert_not_called()

    # DM sent
    mock_bot.send_message.assert_called_once()
    dm_text = mock_bot.send_message.call_args[1]["text"]
    assert "Xush kelibsiz" in dm_text
    assert "VIP Group" in dm_text

    # Log entry
    events = (await db_session.execute(select(JoinEvent))).scalars().all()
    assert len(events) == 1
    assert events[0].status == "approved"
    assert events[0].user_id == 777
    assert events[0].group_id == group.id
    assert events[0].missing_channels is None


@pytest.mark.asyncio
async def test_managed_group_declined(mock_bot, db_session, test_settings):
    """User missing channels -> request kept pending, DM sent with missing list & check button, logged as pending."""
    await add_or_update_protected_group(db_session, chat_id=-100111, title="VIP Group")
    await add_or_update_required_channel(
        db_session, chat_id=-100222, title="Channel One", url="https://t.me/one"
    )
    await add_or_update_required_channel(
        db_session, chat_id=-100333, title="Channel Two", url="https://t.me/two"
    )

    # User is not a member of both (left)
    u = User(id=888, is_bot=False, first_name="Nodir")
    mock_bot.get_chat_member.return_value = ChatMemberLeft.model_construct(
        status="left", user=u
    )

    req = make_request(chat_id=-100111, chat_title="VIP Group", user_id=888, user_name="Nodir")
    await process_chat_join_request(req, mock_bot, db_session, test_settings)

    # Request is kept pending in Telegram, not declined immediately
    mock_bot.decline_chat_join_request.assert_not_called()
    mock_bot.approve_chat_join_request.assert_not_called()

    # DM sent with decline text & buttons (2 channels + 1 check button)
    mock_bot.send_message.assert_called_once()
    dm_text = mock_bot.send_message.call_args[1]["text"]
    assert "Kechirasiz" in dm_text
    assert "Channel One" in dm_text
    assert "Channel Two" in dm_text
    assert "Obuna bo'ldim" in dm_text
    reply_markup = mock_bot.send_message.call_args[1]["reply_markup"]
    assert reply_markup is not None
    assert len(reply_markup.inline_keyboard) == 3  # 2 channel URLs + 1 CheckSub button

    # Log entry
    events = (await db_session.execute(select(JoinEvent))).scalars().all()
    assert len(events) == 1
    assert events[0].status == "pending"
    assert events[0].user_id == 888
    assert "Channel One" in events[0].missing_channels
    assert "Channel Two" in events[0].missing_channels


@pytest.mark.asyncio
async def test_check_subscription_callback_flow(mock_bot, db_session, test_settings):
    """Test clicking 'Obuna bo'ldim' button when still missing vs when joined."""
    from unittest.mock import AsyncMock
    from aiogram.types import CallbackQuery
    from gatebot.handlers.join_requests import on_check_subscription
    from gatebot.keyboards.inline import CheckSubCb

    group = await add_or_update_protected_group(db_session, chat_id=-100111, title="VIP Group")
    await add_or_update_required_channel(
        db_session, chat_id=-100222, title="Channel One", url="https://t.me/one"
    )

    u = User(id=999, is_bot=False, first_name="Temur")

    # 1. User clicks button but still has status='left'
    mock_bot.get_chat_member.return_value = ChatMemberLeft.model_construct(
        status="left", user=u
    )

    cb = AsyncMock(spec=CallbackQuery)
    cb.from_user = u
    cb.message = AsyncMock()
    cb.answer = AsyncMock()
    cb_data = CheckSubCb(group_chat_id=-100111)

    await on_check_subscription(cb, cb_data, mock_bot, db_session, test_settings)

    mock_bot.approve_chat_join_request.assert_not_called()
    cb.answer.assert_called_once()
    assert "Hali barcha kanallarga a'zo bo'lmadingiz" in cb.answer.call_args[0][0]

    # 2. User joins channel, status becomes 'member'
    mock_bot.get_chat_member.return_value = ChatMemberMember.model_construct(
        status="member", user=u
    )
    cb.answer.reset_mock()

    await on_check_subscription(cb, cb_data, mock_bot, db_session, test_settings)

    mock_bot.approve_chat_join_request.assert_called_once_with(chat_id=-100111, user_id=999)
    assert "Tabriklaymiz" in cb.answer.call_args[0][0]

    # Verify approved log entry
    events = (await db_session.execute(select(JoinEvent).where(JoinEvent.user_id == 999))).scalars().all()
    assert len(events) == 1
    assert events[0].status == "approved"
