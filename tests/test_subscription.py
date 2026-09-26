"""Subscription service tests covering all acceptance criteria."""

import pytest
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    ChatMemberAdministrator,
    ChatMemberBanned,
    ChatMemberLeft,
    ChatMemberMember,
    ChatMemberOwner,
    ChatMemberRestricted,
    User,
)

from gatebot.db.models import RequiredChannel
from gatebot.services.notify import clear_alert_history
from gatebot.services.subscription import check_user, clear_cache


@pytest.fixture(autouse=True)
def reset_services():
    clear_cache()
    clear_alert_history()


@pytest.mark.asyncio
async def test_empty_channels_returns_ok(mock_bot):
    """If no active required channels are configured -> everyone approved."""
    res = await check_user(mock_bot, user_id=123, channels=[])
    assert res.ok is True
    assert res.missing == []
    mock_bot.get_chat_member.assert_not_called()


@pytest.mark.asyncio
async def test_member_statuses(mock_bot):
    """Verify owner, admin, regular member are marked subscribed."""
    u = User(id=123, is_bot=False, first_name="Test")
    channel1 = RequiredChannel(id=1, title="Ch1", chat_id=-1001, is_active=True)
    channel2 = RequiredChannel(id=2, title="Ch2", chat_id=-1002, is_active=True)
    channel3 = RequiredChannel(id=3, title="Ch3", chat_id=-1003, is_active=True)

    mock_bot.get_chat_member.side_effect = [
        ChatMemberOwner.model_construct(status=ChatMemberStatus.CREATOR, user=u, is_anonymous=False),
        ChatMemberAdministrator.model_construct(
            status=ChatMemberStatus.ADMINISTRATOR,
            user=u,
            can_be_edited=False,
            is_anonymous=False,
            can_manage_chat=True,
            can_delete_messages=True,
            can_manage_video_chats=True,
            can_restrict_members=True,
            can_promote_members=False,
            can_change_info=False,
            can_invite_users=True,
            can_post_messages=True,
            can_edit_messages=True,
            can_pin_messages=True,
            can_manage_topics=False,
        ),
        ChatMemberMember.model_construct(status=ChatMemberStatus.MEMBER, user=u),
    ]

    res = await check_user(mock_bot, user_id=123, channels=[channel1, channel2, channel3])
    assert res.ok is True
    assert len(res.missing) == 0


@pytest.mark.asyncio
async def test_left_and_kicked_statuses(mock_bot):
    """User status left / kicked on a channel -> not a member."""
    u = User(id=123, is_bot=False, first_name="Test")
    channel1 = RequiredChannel(id=1, title="Ch1", chat_id=-1001, is_active=True)
    channel2 = RequiredChannel(id=2, title="Ch2", chat_id=-1002, is_active=True)

    mock_bot.get_chat_member.side_effect = [
        ChatMemberLeft.model_construct(status=ChatMemberStatus.LEFT, user=u),
        ChatMemberBanned.model_construct(status=ChatMemberStatus.KICKED, user=u, until_date=0),
    ]

    res = await check_user(mock_bot, user_id=123, channels=[channel1, channel2])
    assert res.ok is False
    assert len(res.missing) == 2


@pytest.mark.asyncio
async def test_restricted_statuses(mock_bot):
    """restricted with is_member=True / False handled correctly."""
    u = User(id=123, is_bot=False, first_name="Test")
    ch_ok = RequiredChannel(id=1, title="OkCh", chat_id=-1001, is_active=True)
    ch_fail = RequiredChannel(id=2, title="FailCh", chat_id=-1002, is_active=True)

    # Restricted with is_member=True
    member_ok = ChatMemberRestricted.model_construct(
        status=ChatMemberStatus.RESTRICTED,
        user=u,
        is_member=True,
        until_date=0,
    )

    # Restricted with is_member=False
    member_fail = ChatMemberRestricted.model_construct(
        status=ChatMemberStatus.RESTRICTED,
        user=u,
        is_member=False,
        until_date=0,
    )

    mock_bot.get_chat_member.side_effect = [member_ok, member_fail]

    res = await check_user(mock_bot, user_id=123, channels=[ch_ok, ch_fail])
    assert res.ok is False
    assert len(res.missing) == 1
    assert res.missing[0].id == ch_fail.id


@pytest.mark.asyncio
async def test_positive_cache_hit_and_negative_not_cached(mock_bot):
    """Positive cache hit avoids 2nd API call; negative results never cached."""
    u = User(id=123, is_bot=False, first_name="Test")
    ch_sub = RequiredChannel(id=1, title="Sub", chat_id=-1001, is_active=True)
    ch_unsub = RequiredChannel(id=2, title="Unsub", chat_id=-1002, is_active=True)

    mock_bot.get_chat_member.side_effect = [
        ChatMemberMember.model_construct(status=ChatMemberStatus.MEMBER, user=u),
        ChatMemberLeft.model_construct(status=ChatMemberStatus.LEFT, user=u),
    ]

    # First check: both queried
    res1 = await check_user(mock_bot, user_id=123, channels=[ch_sub, ch_unsub], cache_ttl=60)
    assert res1.ok is False
    assert mock_bot.get_chat_member.call_count == 2

    # Second check: ch_sub is cached (positive), ch_unsub must be re-checked!
    mock_bot.get_chat_member.reset_mock()
    mock_bot.get_chat_member.return_value = ChatMemberLeft.model_construct(status=ChatMemberStatus.LEFT, user=u)

    res2 = await check_user(mock_bot, user_id=123, channels=[ch_sub, ch_unsub], cache_ttl=60)
    assert res2.ok is False
    # Only unsub channel was called again!
    assert mock_bot.get_chat_member.call_count == 1
    call_args = mock_bot.get_chat_member.call_args[1]
    assert call_args["chat_id"] == ch_unsub.chat_id


@pytest.mark.asyncio
async def test_api_error_fails_closed_and_rate_limits_alert(mock_bot):
    """API error checking channel -> fails closed, alert triggered once within 30 min cooldown."""
    ch = RequiredChannel(id=1, title="FaultyChannel", chat_id=-1001, is_active=True)
    admin_ids = [999]

    mock_bot.get_chat_member.side_effect = TelegramBadRequest(
        method="getChatMember", message="Chat not found"
    )

    # 1st call -> fails closed, sends alert to admin
    res1 = await check_user(mock_bot, user_id=123, channels=[ch], admin_ids=admin_ids)
    assert res1.ok is False
    assert len(res1.missing) == 1
    assert mock_bot.send_message.call_count == 1
    assert "FaultyChannel" in mock_bot.send_message.call_args[1]["text"]

    # 2nd call -> fails closed, but alert is rate-limited (not sent again)
    mock_bot.send_message.reset_mock()
    res2 = await check_user(mock_bot, user_id=123, channels=[ch], admin_ids=admin_ids)
    assert res2.ok is False
    assert mock_bot.send_message.call_count == 0
