"""Database CRUD operations."""

from collections.abc import Sequence

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from gatebot.db.models import Admin, JoinEvent, ProtectedGroup, RequiredChannel


# --- Protected Groups ---
async def get_protected_group_by_chat_id(
    session: AsyncSession, chat_id: int
) -> ProtectedGroup | None:
    stmt = select(ProtectedGroup).where(ProtectedGroup.chat_id == chat_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_protected_group_by_id(
    session: AsyncSession, group_id: int
) -> ProtectedGroup | None:
    stmt = select(ProtectedGroup).where(ProtectedGroup.id == group_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_all_protected_groups(
    session: AsyncSession, active_only: bool = False
) -> Sequence[ProtectedGroup]:
    stmt = select(ProtectedGroup)
    if active_only:
        stmt = stmt.where(ProtectedGroup.is_active.is_(True))
    stmt = stmt.order_by(ProtectedGroup.id.asc())
    result = await session.execute(stmt)
    return result.scalars().all()


async def add_or_update_protected_group(
    session: AsyncSession, chat_id: int, title: str
) -> ProtectedGroup:
    group = await get_protected_group_by_chat_id(session, chat_id)
    if group:
        group.title = title
        group.is_active = True
    else:
        group = ProtectedGroup(chat_id=chat_id, title=title, is_active=True)
        session.add(group)
    await session.flush()
    return group


async def set_protected_group_active(
    session: AsyncSession, chat_id: int, is_active: bool
) -> bool:
    stmt = (
        update(ProtectedGroup)
        .where(ProtectedGroup.chat_id == chat_id)
        .values(is_active=is_active)
    )
    result = await session.execute(stmt)
    return result.rowcount > 0


async def update_protected_group_chat_id(
    session: AsyncSession, old_chat_id: int, new_chat_id: int
) -> bool:
    stmt = (
        update(ProtectedGroup)
        .where(ProtectedGroup.chat_id == old_chat_id)
        .values(chat_id=new_chat_id)
    )
    result = await session.execute(stmt)
    return result.rowcount > 0


async def delete_protected_group(session: AsyncSession, chat_id: int) -> bool:
    stmt = delete(ProtectedGroup).where(ProtectedGroup.chat_id == chat_id)
    result = await session.execute(stmt)
    return result.rowcount > 0


# --- Required Channels ---
async def get_required_channel_by_chat_id(
    session: AsyncSession, chat_id: int
) -> RequiredChannel | None:
    stmt = select(RequiredChannel).where(RequiredChannel.chat_id == chat_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_required_channel_by_id(
    session: AsyncSession, channel_id: int
) -> RequiredChannel | None:
    stmt = select(RequiredChannel).where(RequiredChannel.id == channel_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_active_required_channels(
    session: AsyncSession,
) -> Sequence[RequiredChannel]:
    stmt = (
        select(RequiredChannel)
        .where(RequiredChannel.is_active.is_(True))
        .order_by(RequiredChannel.sort_order.asc(), RequiredChannel.id.asc())
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_all_required_channels(
    session: AsyncSession,
) -> Sequence[RequiredChannel]:
    stmt = select(RequiredChannel).order_by(
        RequiredChannel.sort_order.asc(), RequiredChannel.id.asc()
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def add_or_update_required_channel(
    session: AsyncSession, chat_id: int, title: str, url: str | None = None
) -> RequiredChannel:
    channel = await get_required_channel_by_chat_id(session, chat_id)
    if channel:
        channel.title = title
        channel.is_active = True
        if url is not None:
            channel.url = url
    else:
        channel = RequiredChannel(chat_id=chat_id, title=title, url=url, is_active=True)
        session.add(channel)
    await session.flush()
    return channel


async def set_required_channel_active(
    session: AsyncSession, chat_id: int, is_active: bool
) -> bool:
    stmt = (
        update(RequiredChannel)
        .where(RequiredChannel.chat_id == chat_id)
        .values(is_active=is_active)
    )
    result = await session.execute(stmt)
    return result.rowcount > 0


async def set_required_channel_url(
    session: AsyncSession, chat_id: int, url: str | None
) -> bool:
    stmt = (
        update(RequiredChannel)
        .where(RequiredChannel.chat_id == chat_id)
        .values(url=url)
    )
    result = await session.execute(stmt)
    return result.rowcount > 0


async def delete_required_channel(session: AsyncSession, chat_id: int) -> bool:
    stmt = delete(RequiredChannel).where(RequiredChannel.chat_id == chat_id)
    result = await session.execute(stmt)
    return result.rowcount > 0


# --- Admins ---
async def is_admin(
    session: AsyncSession, tg_id: int, super_admin_ids: list[int]
) -> bool:
    if tg_id in super_admin_ids:
        return True
    stmt = select(Admin).where(Admin.tg_id == tg_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def add_admin(
    session: AsyncSession, tg_id: int, added_by: int | None = None
) -> Admin:
    admin = await session.get(Admin, tg_id)
    if not admin:
        admin = Admin(tg_id=tg_id, added_by=added_by)
        session.add(admin)
        await session.flush()
    return admin


async def remove_admin(session: AsyncSession, tg_id: int) -> bool:
    stmt = delete(Admin).where(Admin.tg_id == tg_id)
    result = await session.execute(stmt)
    return result.rowcount > 0


async def get_all_admins(session: AsyncSession) -> Sequence[Admin]:
    stmt = select(Admin).order_by(Admin.added_at.asc())
    result = await session.execute(stmt)
    return result.scalars().all()


# --- Join Events ---
async def log_join_event(
    session: AsyncSession,
    group_id: int,
    user_id: int,
    user_name: str | None,
    status: str,
    missing_channels: str | None = None,
) -> JoinEvent:
    event = JoinEvent(
        group_id=group_id,
        user_id=user_id,
        user_name=user_name,
        status=status,
        missing_channels=missing_channels,
    )
    session.add(event)
    await session.flush()
    return event
