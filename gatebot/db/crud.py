"""Database CRUD operations and statistics."""

from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select, update
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


async def update_channel_sort_order(
    session: AsyncSession, channel_id: int, delta: int
) -> bool:
    channel = await get_required_channel_by_id(session, channel_id)
    if not channel:
        return False
    channel.sort_order += delta
    await session.flush()
    return True


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


# --- Join Events & Statistics ---
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


async def get_join_stats(session: AsyncSession) -> dict:
    """Calculate all-time and 7-day statistics from join_events."""
    now = datetime.now(UTC)
    seven_days_ago = now - timedelta(days=7)

    # All time totals
    stmt_all = select(JoinEvent.status, func.count(JoinEvent.id)).group_by(JoinEvent.status)
    res_all = await session.execute(stmt_all)
    all_counts = dict(res_all.all())
    total_approved = all_counts.get("approved", 0)
    total_declined = all_counts.get("declined", 0)

    # 7-day totals
    stmt_7d = (
        select(JoinEvent.status, func.count(JoinEvent.id))
        .where(JoinEvent.created_at >= seven_days_ago)
        .group_by(JoinEvent.status)
    )
    res_7d = await session.execute(stmt_7d)
    counts_7d = dict(res_7d.all())
    approved_7d = counts_7d.get("approved", 0)
    declined_7d = counts_7d.get("declined", 0)

    # Per-group breakdown
    groups = await get_all_protected_groups(session)
    group_stats = []
    for g in groups:
        stmt_g = (
            select(JoinEvent.status, func.count(JoinEvent.id))
            .where(JoinEvent.group_id == g.id)
            .group_by(JoinEvent.status)
        )
        res_g = await session.execute(stmt_g)
        g_counts = dict(res_g.all())
        group_stats.append({
            "title": g.title,
            "is_active": g.is_active,
            "approved": g_counts.get("approved", 0),
            "declined": g_counts.get("declined", 0),
        })

    # Most common missing channels
    stmt_missing = select(JoinEvent.missing_channels).where(
        JoinEvent.status == "declined", JoinEvent.missing_channels.isnot(None)
    )
    res_missing = await session.execute(stmt_missing)
    counter: Counter[str] = Counter()
    for row in res_missing.scalars():
        if row:
            for item in row.split(","):
                clean = item.strip()
                if clean:
                    counter[clean] += 1
    top_missing = counter.most_common(5)

    return {
        "total_approved": total_approved,
        "total_declined": total_declined,
        "approved_7d": approved_7d,
        "declined_7d": declined_7d,
        "groups": group_stats,
        "top_missing": top_missing,
    }
