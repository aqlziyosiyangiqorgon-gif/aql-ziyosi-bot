"""Background scheduler unit tests."""

import pytest
from aiogram.enums import ChatMemberStatus
from aiogram.types import ChatMemberAdministrator, ChatMemberLeft, User

from gatebot.db.crud import (
    add_or_update_protected_group,
    add_or_update_required_channel,
)
from gatebot.services.scheduler import daily_permission_audit, setup_scheduler


def test_setup_scheduler(mock_bot, test_settings):
    """Verify scheduler registers daily backup and audit jobs."""
    scheduler = setup_scheduler(mock_bot, test_settings)
    job_ids = [job.id for job in scheduler.get_jobs()]
    assert "daily_backup" in job_ids
    assert "daily_permission_audit" in job_ids


@pytest.mark.asyncio
async def test_daily_permission_audit_no_issues(mock_bot, db_session, test_settings):
    """When all permissions are valid, no warning alert is sent."""
    await add_or_update_protected_group(db_session, chat_id=-1001, title="Group 1")
    await add_or_update_required_channel(db_session, chat_id=-1002, title="Channel 1")

    bot_user = User(id=9999, is_bot=True, first_name="GateBot")
    mock_bot.get_me.return_value = bot_user

    admin_member = ChatMemberAdministrator.model_construct(
        status=ChatMemberStatus.ADMINISTRATOR,
        user=bot_user,
        can_invite_users=True,
    )
    mock_bot.get_chat_member.return_value = admin_member

    await daily_permission_audit(mock_bot, test_settings)
    mock_bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_daily_permission_audit_with_issues(mock_bot, db_session, test_settings):
    """When issues exist, single consolidated alert is dispatched to admins."""
    await add_or_update_protected_group(db_session, chat_id=-1001, title="Faulty Group")
    await add_or_update_required_channel(db_session, chat_id=-1002, title="Kicked Channel")

    bot_user = User(id=9999, is_bot=True, first_name="GateBot")
    mock_bot.get_me.return_value = bot_user

    # Group: admin but missing invite rights
    grp_member = ChatMemberAdministrator.model_construct(
        status=ChatMemberStatus.ADMINISTRATOR,
        user=bot_user,
        can_invite_users=False,
    )
    # Channel: kicked out
    chn_member = ChatMemberLeft.model_construct(
        status=ChatMemberStatus.LEFT,
        user=bot_user,
    )
    mock_bot.get_chat_member.side_effect = [grp_member, chn_member]

    await daily_permission_audit(mock_bot, test_settings)

    # Verified sent consolidated alert
    assert mock_bot.send_message.call_count >= 1
    alert_text = mock_bot.send_message.call_args[1]["text"]
    assert "Kunlik tekshiruv: Aniqlangan muammolar" in alert_text
    assert "Faulty Group" in alert_text
    assert "Kicked Channel" in alert_text
