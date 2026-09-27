"""Database CRUD operations and statistics."""

from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from gatebot.db.models import Admin, BotUser, JoinEvent, ProtectedGroup, RequiredChannel


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

    # Per-group breakdown (single query)
    groups = await get_all_protected_groups(session)
    stmt_per_group = (
        select(JoinEvent.group_id, JoinEvent.status, func.count(JoinEvent.id))
        .group_by(JoinEvent.group_id, JoinEvent.status)
    )
    res_per_group = await session.execute(stmt_per_group)
    group_counts: dict[int, dict[str, int]] = {}
    for group_id, status, count in res_per_group.all():
        group_counts.setdefault(group_id, {})[status] = count

    group_stats = []
    for g in groups:
        g_counts = group_counts.get(g.id, {})
        approved = g_counts.get("approved", 0)
        declined = g_counts.get("declined", 0)
        total = approved + declined
        group_stats.append({
            "group_id": g.id,
            "chat_id": g.chat_id,
            "title": g.title,
            "is_active": g.is_active,
            "approved": approved,
            "declined": declined,
            "total": total,
        })

    # Sort groups by total requests descending (Top active groups)
    top_groups = sorted(group_stats, key=lambda x: x["total"], reverse=True)

    # Most common missing channels
    stmt_missing = select(JoinEvent.missing_channels).where(
        JoinEvent.status.in_(["declined", "pending"]), JoinEvent.missing_channels.isnot(None)
    )
    res_missing = await session.execute(stmt_missing)
    counter: Counter[str] = Counter()
    for row in res_missing.scalars():
        if row:
            sep = " || " if " || " in row else ","
            for item in row.split(sep):
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
        "top_groups": top_groups,
        "top_missing": top_missing,
    }


async def get_daily_join_stats(session: AsyncSession, days: int = 30) -> list[dict]:
    """Return daily join request breakdown per date and group for reports."""
    now = datetime.now(UTC)
    start_date = now - timedelta(days=days)

    date_col = func.date(JoinEvent.created_at)
    stmt = (
        select(
            date_col.label("event_date"),
            JoinEvent.group_id,
            JoinEvent.status,
            func.count(JoinEvent.id),
        )
        .where(JoinEvent.created_at >= start_date)
        .group_by(date_col, JoinEvent.group_id, JoinEvent.status)
        .order_by(date_col.desc())
    )
    res = await session.execute(stmt)

    groups_map = {g.id: g.title for g in await get_all_protected_groups(session)}

    # Aggregate by (event_date, group_id)
    aggregated: dict[tuple[str, int], dict] = {}
    for event_date, group_id, status, count in res.all():
        key = (str(event_date), group_id)
        if key not in aggregated:
            aggregated[key] = {
                "date": str(event_date),
                "group_id": group_id,
                "group_title": groups_map.get(group_id, f"Guruh {group_id}"),
                "approved": 0,
                "declined": 0,
                "total": 0,
            }
        if status == "approved":
            aggregated[key]["approved"] += count
        elif status in ("declined", "pending"):
            aggregated[key]["declined"] += count
        aggregated[key]["total"] += count

    return list(aggregated.values())


# --- Bot Users ---
async def add_or_update_user(
    session: AsyncSession,
    tg_id: int,
    first_name: str | None = None,
    username: str | None = None,
) -> BotUser:
    user = await session.get(BotUser, tg_id)
    if user:
        if first_name is not None:
            user.first_name = first_name
        if username is not None:
            user.username = username
        user.is_bot_blocked = False
    else:
        user = BotUser(
            tg_id=tg_id,
            first_name=first_name,
            username=username,
            is_bot_blocked=False,
        )
        session.add(user)
    await session.flush()
    return user


async def set_user_blocked(
    session: AsyncSession, tg_id: int, is_blocked: bool = True
) -> bool:
    stmt = (
        update(BotUser)
        .where(BotUser.tg_id == tg_id)
        .values(is_bot_blocked=is_blocked)
    )
    result = await session.execute(stmt)
    return result.rowcount > 0


async def get_active_broadcast_users(session: AsyncSession) -> Sequence[BotUser]:
    stmt = select(BotUser).where(BotUser.is_bot_blocked.is_(False))
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_broadcast_counts(session: AsyncSession) -> dict[str, int]:
    stmt_users = select(func.count(BotUser.tg_id)).where(BotUser.is_bot_blocked.is_(False))
    res_users = await session.execute(stmt_users)
    users_count = res_users.scalar() or 0

    stmt_groups = select(func.count(ProtectedGroup.id)).where(ProtectedGroup.is_active.is_(True))
    res_groups = await session.execute(stmt_groups)
    groups_count = res_groups.scalar() or 0

    return {
        "users": users_count,
        "groups": groups_count,
        "total": users_count + groups_count,
    }
