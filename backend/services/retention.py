"""Bound user-facing history while preserving active bookings and admin audit rows."""
from datetime import timedelta

from sqlalchemy import and_, delete, func, or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.db import utcnow
from backend.models import AdminNotification, Booking, UserNotification

TERMINAL_STATUSES = ("cancelled", "watched")
READ_NOTICE_DAYS = 30
UNREAD_NOTICE_DAYS = 90
HISTORY_DAYS = 180


async def prune_viewer_records(session: AsyncSession, user_id: int) -> int:
    now = utcnow()
    read_cutoff = now - timedelta(days=READ_NOTICE_DAYS)
    unread_cutoff = now - timedelta(days=UNREAD_NOTICE_DAYS)
    history_cutoff = now - timedelta(days=HISTORY_DAYS)
    user_result = await session.execute(
        delete(UserNotification).where(
            UserNotification.user_id == user_id,
            or_(
                UserNotification.created_at < unread_cutoff,
                and_(UserNotification.is_read.is_(True), UserNotification.created_at < read_cutoff),
            ),
        )
    )
    history_result = await session.execute(
        update(Booking)
        .where(
            Booking.user_id == user_id,
            Booking.status.in_(TERMINAL_STATUSES),
            Booking.viewer_hidden_at.is_(None),
            func.coalesce(Booking.completed_at, Booking.created_at) < history_cutoff,
        )
        .values(viewer_hidden_at=now, version=Booking.version + 1)
    )
    changed = (user_result.rowcount or 0) + (history_result.rowcount or 0)
    if changed:
        await session.commit()
    return changed


async def prune_admin_records(session: AsyncSession) -> int:
    now = utcnow()
    read_cutoff = now - timedelta(days=READ_NOTICE_DAYS)
    unread_cutoff = now - timedelta(days=UNREAD_NOTICE_DAYS)
    result = await session.execute(
        delete(AdminNotification).where(
            or_(
                AdminNotification.created_at < unread_cutoff,
                and_(AdminNotification.is_read.is_(True), AdminNotification.created_at < read_cutoff),
            )
        )
    )
    if result.rowcount:
        await session.commit()
    return result.rowcount or 0


async def hide_viewer_history(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(
        update(Booking)
        .where(
            Booking.user_id == user_id,
            Booking.status.in_(TERMINAL_STATUSES),
            Booking.viewer_hidden_at.is_(None),
        )
        .values(viewer_hidden_at=utcnow(), version=Booking.version + 1)
    )
    await session.commit()
    return result.rowcount or 0
