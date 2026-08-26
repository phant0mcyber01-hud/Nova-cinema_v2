"""The generic schedule: which dates and which fixed times can be booked.

A slot is a date plus one of the administrator's times.  There is no film in any
of it -- `slot_templates` is global, and the booking window comes from the
settings row, so a day is open because the cinema is open, not because somebody
scheduled a particular movie on it.
"""
from __future__ import annotations

import re
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import DEFAULT_SLOT_TIMES, TIME_PATTERN
from backend.core.db import SessionLocal
from backend.models import SlotTemplate
from backend.services.booking import cinema_now, session_has_started
from backend.services.settings import get_settings

__all__ = [
    "active_slot_times",
    "booking_window",
    "ensure_slot_is_bookable",
    "slot_templates",
]


async def _seed_default_slots() -> None:
    """Create the five fixed times on first use.

    Done in an independent session for the same reason as the settings row: two
    parallel first requests would both find the table empty, and the unique key
    on `start_time` must be allowed to kill the loser without poisoning the
    caller's transaction.
    """
    async with SessionLocal() as creator:
        creator.add_all(
            SlotTemplate(start_time=start_time, is_active=True, sort_order=order)
            for order, start_time in enumerate(DEFAULT_SLOT_TIMES)
        )
        try:
            await creator.commit()
        except IntegrityError:
            await creator.rollback()


async def slot_templates(session: AsyncSession, *, active_only: bool = False) -> list[SlotTemplate]:
    """Every configured time, seeding the defaults the first time it is asked."""
    query = select(SlotTemplate).order_by(SlotTemplate.sort_order, SlotTemplate.start_time)
    rows = list(await session.scalars(query))
    if not rows:
        await _seed_default_slots()
        rows = list(await session.scalars(query))
    if active_only:
        rows = [item for item in rows if item.is_active]
    return rows


async def active_slot_times(session: AsyncSession) -> list[str]:
    return [item.start_time for item in await slot_templates(session, active_only=True)]


async def booking_window(session: AsyncSession) -> list[str]:
    """The dates the cinema is open for requests, in the cinema's own time."""
    settings = await get_settings(session)
    first_day = cinema_now(settings.timezone_offset_minutes).date()
    return [
        (first_day + timedelta(days=offset)).isoformat()
        for offset in range(max(settings.booking_days_ahead, 1))
    ]


async def bookable_times(session: AsyncSession, show_date: str) -> list[str]:
    """The configured times for that date that have not started yet."""
    offset = (await get_settings(session)).timezone_offset_minutes
    return [
        start_time
        for start_time in await active_slot_times(session)
        if not session_has_started(show_date, start_time, offset)
    ]


async def ensure_slot_is_bookable(session: AsyncSession, show_date: str, start_time: str) -> None:
    """Gate for every write on the generic flow.

    Refuses a date outside the admin's window, a time the administrator has not
    configured, and a slot that has already begun in the cinema's own time.
    """
    if not re.fullmatch(TIME_PATTERN, start_time):
        raise HTTPException(404, "Slot not found")
    if show_date not in await booking_window(session):
        raise HTTPException(404, "Date is not open for booking")
    if start_time not in await active_slot_times(session):
        raise HTTPException(404, "Slot not found")
    offset = (await get_settings(session)).timezone_offset_minutes
    if session_has_started(show_date, start_time, offset):
        raise HTTPException(404, "Slot already started")
