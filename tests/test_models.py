"""Database models and CRUD unit tests."""

import pytest

from gatebot.db.crud import (
    add_admin,
    add_or_update_protected_group,
    add_or_update_required_channel,
    delete_protected_group,
    delete_required_channel,
    get_all_admins,
    get_all_protected_groups,
    get_all_required_channels,
    log_join_event,
    remove_admin,
    set_protected_group_active,
    set_required_channel_active,
    set_required_channel_url,
)


@pytest.mark.asyncio
async def test_protected_groups_crud(db_session):
    g1 = await add_or_update_protected_group(db_session, chat_id=-1001, title="Group 1")
    assert g1.id is not None
    assert g1.is_active is True

    # Toggle active
    await set_protected_group_active(db_session, -1001, False)
    all_active = await get_all_protected_groups(db_session, active_only=True)
    assert len(all_active) == 0

    all_groups = await get_all_protected_groups(db_session, active_only=False)
    assert len(all_groups) == 1

    # Delete
    await delete_protected_group(db_session, -1001)
    assert len(await get_all_protected_groups(db_session)) == 0


@pytest.mark.asyncio
async def test_required_channels_crud(db_session):
    c1 = await add_or_update_required_channel(
        db_session, chat_id=-2001, title="Chan 1", url="https://t.me/c1"
    )
    assert c1.id is not None
    assert c1.url == "https://t.me/c1"

    await set_required_channel_url(db_session, -2001, "https://t.me/new_c1")
    channels = await get_all_required_channels(db_session)
    assert channels[0].url == "https://t.me/new_c1"

    await set_required_channel_active(db_session, -2001, False)
    assert len(channels) == 1

    await delete_required_channel(db_session, -2001)
    assert len(await get_all_required_channels(db_session)) == 0


@pytest.mark.asyncio
async def test_admins_and_events_crud(db_session):
    # Admins
    a = await add_admin(db_session, tg_id=55555, added_by=111)
    assert a.tg_id == 55555
    admins = await get_all_admins(db_session)
    assert len(admins) == 1

    await remove_admin(db_session, 55555)
    assert len(await get_all_admins(db_session)) == 0

    # Join Event log
    g = await add_or_update_protected_group(db_session, chat_id=-3001, title="Test Group")
    ev = await log_join_event(
        db_session,
        group_id=g.id,
        user_id=777,
        user_name="Bob",
        status="declined",
        missing_channels="Chan A, Chan B",
    )
    assert ev.id is not None
    assert ev.status == "declined"
    assert ev.missing_channels == "Chan A, Chan B"
