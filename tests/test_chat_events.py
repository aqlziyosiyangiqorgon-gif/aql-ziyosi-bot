"""Chat events and auto-detection unit tests."""

from unittest.mock import AsyncMock

import pytest
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.types import (
    Chat,
    ChatMemberAdministrator,
    ChatMemberLeft,
    ChatMemberMember,
    ChatMemberUpdated,
    Message,
    User,
)

from gatebot.db.crud import (
    add_or_update_protected_group,
    add_or_update_required_channel,
    get_protected_group_by_chat_id,
    get_required_channel_by_chat_id,
)
from gatebot.handlers.chat_events import (
    on_bot_promoted_to_admin,
    on_bot_removed_or_demoted,
    on_channel_confirm,
    on_group_confirm,
    on_group_migration,
    on_group_reject,
    on_service_join_leave_message,
)
from gatebot.services.notify import clear_alert_history


@pytest.fixture(autouse=True)
def reset_state():
    clear_alert_history()


def make_chat_member_updated(
    chat_type: ChatType,
    chat_id: int,
    chat_title: str,
    inviter_id: int,
    new_status: ChatMemberStatus,
    old_status: ChatMemberStatus = ChatMemberStatus.MEMBER,
    can_invite: bool = True,
) -> ChatMemberUpdated:
    bot_user = User(id=9999, is_bot=True, first_name="Bot")
    inviter = User(id=inviter_id, is_bot=False, first_name="Admin")
    chat = Chat(id=chat_id, type=chat_type, title=chat_title)

    if new_status == ChatMemberStatus.ADMINISTRATOR:
        new_cm = ChatMemberAdministrator.model_construct(
            status=ChatMemberStatus.ADMINISTRATOR,
            user=bot_user,
            can_be_edited=False,
            is_anonymous=False,
            can_manage_chat=True,
            can_delete_messages=True,
            can_manage_video_chats=True,
            can_restrict_members=True,
            can_promote_members=False,
            can_change_info=False,
            can_invite_users=can_invite,
            can_post_messages=True,
            can_edit_messages=True,
            can_pin_messages=True,
            can_manage_topics=False,
        )
    elif new_status == ChatMemberStatus.LEFT:
        new_cm = ChatMemberLeft.model_construct(status=ChatMemberStatus.LEFT, user=bot_user)
    else:
        new_cm = ChatMemberMember.model_construct(status=ChatMemberStatus.MEMBER, user=bot_user)

    old_cm = ChatMemberMember.model_construct(status=ChatMemberStatus.MEMBER, user=bot_user)

    return ChatMemberUpdated(
        chat=chat,
        from_user=inviter,
        date=1700000000,
        old_chat_member=old_cm,
        new_chat_member=new_cm,
    )


@pytest.mark.asyncio
async def test_non_admin_adds_bot_leaves_chat(mock_bot, db_session, test_settings):
    """Non-admin adds the bot -> bot leaves automatically, alerts admins."""
    event = make_chat_member_updated(
        chat_type=ChatType.SUPERGROUP,
        chat_id=-100555,
        chat_title="Random Group",
        inviter_id=12345,  # NOT in ADMIN_IDS, not in DB
        new_status=ChatMemberStatus.ADMINISTRATOR,
    )

    await on_bot_promoted_to_admin(event, mock_bot, db_session, test_settings)

    mock_bot.leave_chat.assert_called_once_with(-100555)
    # Alerts sent to super admins
    assert mock_bot.send_message.call_count >= 1


@pytest.mark.asyncio
async def test_admin_adds_bot_to_group_prompts_confirmation(mock_bot, db_session, test_settings):
    """Admin adds bot to group -> prompt DM sent with confirmation buttons."""
    event = make_chat_member_updated(
        chat_type=ChatType.SUPERGROUP,
        chat_id=-100666,
        chat_title="Target Group",
        inviter_id=test_settings.ADMIN_IDS[0],
        new_status=ChatMemberStatus.ADMINISTRATOR,
        can_invite=True,
    )

    await on_bot_promoted_to_admin(event, mock_bot, db_session, test_settings)

    mock_bot.leave_chat.assert_not_called()
    mock_bot.send_message.assert_called_once()
    call_args = mock_bot.send_message.call_args[1]
    assert call_args["chat_id"] == test_settings.ADMIN_IDS[0]
    assert "Target Group" in call_args["text"]
    assert "Guruh avtomatik himoyaga olindi" in call_args["text"]

    group = await get_protected_group_by_chat_id(db_session, -100666)
    assert group is not None
    assert group.is_active is True



@pytest.mark.asyncio
async def test_group_confirmation_callbacks(mock_bot, db_session, test_settings):
    """Confirming adds to DB; rejecting ignores."""
    mock_bot.get_chat.return_value = Chat(id=-100777, type=ChatType.SUPERGROUP, title="Confirmed Group")

    admin_user = User(id=test_settings.ADMIN_IDS[0], is_bot=False, first_name="Admin")

    # Confirm
    msg_mock = AsyncMock()
    msg_mock.edit_text = AsyncMock()
    cb_confirm = AsyncMock()
    cb_confirm.data = "group_add:-100777"
    cb_confirm.message = msg_mock
    cb_confirm.answer = AsyncMock()
    cb_confirm.from_user = admin_user

    await on_group_confirm(cb_confirm, mock_bot, db_session, test_settings)
    group = await get_protected_group_by_chat_id(db_session, -100777)
    assert group is not None
    assert group.title == "Confirmed Group"
    assert group.is_active is True

    # Reject
    cb_reject = AsyncMock()
    cb_reject.data = "group_reject:-100888"
    cb_reject.message = msg_mock
    cb_reject.answer = AsyncMock()
    cb_reject.from_user = admin_user

    await on_group_reject(cb_reject, mock_bot, db_session, test_settings)
    group_rej = await get_protected_group_by_chat_id(db_session, -100888)
    assert group_rej is None


@pytest.mark.asyncio
async def test_channel_confirmation_callback(mock_bot, db_session, test_settings):
    """Confirming adds channel to DB."""
    mock_tg_channel = Chat(
        id=-100999,
        type=ChatType.CHANNEL,
        title="Official News",
        username="official_news",
        invite_link=None,
    )
    mock_bot.get_chat.return_value = mock_tg_channel

    admin_user = User(id=test_settings.ADMIN_IDS[0], is_bot=False, first_name="Admin")

    msg_mock = AsyncMock()
    msg_mock.edit_text = AsyncMock()
    cb = AsyncMock()
    cb.data = "chan_add:-100999"
    cb.message = msg_mock
    cb.answer = AsyncMock()
    cb.from_user = admin_user

    await on_channel_confirm(cb, mock_bot, db_session, test_settings)
    ch = await get_required_channel_by_chat_id(db_session, -100999)
    assert ch is not None
    assert ch.title == "Official News"
    assert ch.url == "https://t.me/official_news"


@pytest.mark.asyncio
async def test_bot_removed_sets_inactive_and_alerts(mock_bot, db_session, test_settings):
    """Bot removed from protected group or channel sets is_active=False and alerts admin."""
    await add_or_update_protected_group(db_session, chat_id=-100111, title="Test Group")
    await add_or_update_required_channel(db_session, chat_id=-100222, title="Test Channel")

    # Bot removed from group
    event_grp = make_chat_member_updated(
        chat_type=ChatType.SUPERGROUP,
        chat_id=-100111,
        chat_title="Test Group",
        inviter_id=test_settings.ADMIN_IDS[0],
        new_status=ChatMemberStatus.LEFT,
    )
    await on_bot_removed_or_demoted(event_grp, mock_bot, db_session, test_settings)
    grp = await get_protected_group_by_chat_id(db_session, -100111)
    assert grp.is_active is False

    # Bot removed from channel
    event_chn = make_chat_member_updated(
        chat_type=ChatType.CHANNEL,
        chat_id=-100222,
        chat_title="Test Channel",
        inviter_id=test_settings.ADMIN_IDS[0],
        new_status=ChatMemberStatus.LEFT,
    )
    await on_bot_removed_or_demoted(event_chn, mock_bot, db_session, test_settings)
    chn = await get_required_channel_by_chat_id(db_session, -100222)
    assert chn.is_active is False


@pytest.mark.asyncio
async def test_supergroup_migration(db_session):
    """Basic group -> supergroup migration updates chat_id."""
    await add_or_update_protected_group(db_session, chat_id=-500, title="Migrating Group")

    msg = AsyncMock(spec=Message)
    msg.chat = Chat(id=-500, type=ChatType.GROUP)
    msg.migrate_to_chat_id = -100500

    await on_group_migration(msg, db_session)

    old_grp = await get_protected_group_by_chat_id(db_session, -500)
    assert old_grp is None
    new_grp = await get_protected_group_by_chat_id(db_session, -100500)
    assert new_grp is not None
    assert new_grp.title == "Migrating Group"


@pytest.mark.asyncio
async def test_auto_delete_service_messages(db_session):
    """Joined / left service messages are automatically deleted in protected groups."""
    await add_or_update_protected_group(db_session, chat_id=-100111, title="Active Group")

    # 1. Message in protected group -> deleted
    msg_managed = AsyncMock(spec=Message)
    msg_managed.chat = Chat(id=-100111, type=ChatType.SUPERGROUP)
    msg_managed.delete = AsyncMock()

    await on_service_join_leave_message(msg_managed, db_session)
    msg_managed.delete.assert_called_once()

    # 2. Message in unmanaged group -> ignored
    msg_unmanaged = AsyncMock(spec=Message)
    msg_unmanaged.chat = Chat(id=-100999, type=ChatType.SUPERGROUP)
    msg_unmanaged.delete = AsyncMock()

    await on_service_join_leave_message(msg_unmanaged, db_session)
    msg_unmanaged.delete.assert_not_called()
