"""Screening lookup and booking-side rules shared by the public endpoints."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import BLOCKING_STATUSES
from backend.core.db import utcnow
from backend.models import Booking, Movie, Show
from backend.services.settings import get_settings

__all__ = [
    "BLOCKING_STATUSES",
    "cinema_now",
    "ensure_show",
    "movie_schedule",
    "seats_taken_by_others",
    "session_has_ended",
    "session_has_started",
    "show_times_by_movie",
    "upcoming_show_times",
]


def cinema_now(offset_minutes: int, now: datetime | None = None) -> datetime:
    """Wall-clock time at the cinema.

    The server runs in UTC and the cinema does not, so "today" and "already
    started" are only meaningful once the offset from the settings row is
    applied. Without it the schedule rolls over at 05:00 local time.
    """
    return (now or utcnow()).replace(tzinfo=None) + timedelta(minutes=offset_minutes)


def session_has_started(
    show_date: str, start_time: str, offset_minutes: int, now: datetime | None = None
) -> bool:
    """True once the screening has begun in the cinema's own time.

    A request is worth nothing until the administrator has phoned the viewer
    back, so a screening that is already running cannot be booked — and must
    not be offered in the first place.
    """
    try:
        start = datetime.fromisoformat(f"{show_date}T{start_time}")
    except ValueError:
        return False
    return cinema_now(offset_minutes, now) >= start


async def ensure_show(session: AsyncSession, movie_id: int, show_date: str, start_time: str) -> Show:
    """Reject anything that is not a published movie on an active screening.

    Replaces the old check that accepted any well-formed HH:MM, so the schedule
    is now genuinely controlled from the admin panel.
    """
    movie = await session.get(Movie, movie_id)
    if movie is None or not movie.is_published:
        raise HTTPException(404, "Movie not found")
    # A screening that has already been and gone must not be bookable, even
    # though the admin may keep the row for reporting.  The comparison is made
    # in the cinema's own time: a server in UTC still thinks it is yesterday
    # while the last screening of the evening is already over.
    settings = await get_settings(session)
    offset = settings.timezone_offset_minutes
    if show_date < cinema_now(offset).date().isoformat():
        raise HTTPException(404, "Session not found")
    if session_has_started(show_date, start_time, offset):
        raise HTTPException(404, "Session already started")
    show = await session.scalar(
        select(Show).where(
            Show.movie_id == movie_id,
            Show.show_date == show_date,
            Show.start_time == start_time,
            Show.status == "active",
        )
    )
    if show is None:
        raise HTTPException(404, "Session not found")
    return show


async def upcoming_show_times(session: AsyncSession, movie_id: int, show_date: str) -> list[str]:
    """Times still open for a request on that date, in the cinema's own time."""
    offset = (await get_settings(session)).timezone_offset_minutes
    if show_date < cinema_now(offset).date().isoformat():
        return []
    rows = await session.scalars(
        select(Show.start_time)
        .where(Show.movie_id == movie_id, Show.show_date == show_date, Show.status == "active")
        .order_by(Show.start_time)
    )
    return [time for time in rows if not session_has_started(show_date, time, offset)]


async def show_times_by_movie(
    session: AsyncSession,
    movie_ids: list[int],
    show_date: str | None = None,
    *,
    upcoming_only: bool = False,
) -> dict[int, list[str]]:
    """One query for the whole catalog instead of a query per movie.

    `upcoming_only` is what the viewer sees: past dates and screenings that
    have already begun drop out. The admin panel leaves it off — the schedule
    it manages includes everything that has been.
    """
    if not movie_ids:
        return {}
    query = select(Show.movie_id, Show.show_date, Show.start_time).where(
        Show.movie_id.in_(movie_ids), Show.status == "active"
    )
    if show_date is not None:
        query = query.where(Show.show_date == show_date)
    offset = (await get_settings(session)).timezone_offset_minutes if upcoming_only else 0
    today = cinema_now(offset).date().isoformat() if upcoming_only else ""
    grouped: dict[int, set[str]] = defaultdict(set)
    for movie_id, day, start_time in await session.execute(query):
        if upcoming_only and (day < today or session_has_started(day, start_time, offset)):
            continue
        grouped[movie_id].add(start_time)
    return {movie_id: sorted(times) for movie_id, times in grouped.items()}


async def movie_schedule(session: AsyncSession, movie_id: int, days: int) -> list[dict[str, object]]:
    """Upcoming screenings grouped by date, for the movie card.

    Past dates are skipped and the window matches the admin-configured
    `booking_days_ahead`, so the card never offers a slot that cannot be booked.
    """
    offset = (await get_settings(session)).timezone_offset_minutes
    today = cinema_now(offset).date()
    last_day = (today + timedelta(days=max(days, 1) - 1)).isoformat()
    rows = await session.execute(
        select(Show.show_date, Show.start_time)
        .where(
            Show.movie_id == movie_id,
            Show.status == "active",
            Show.show_date >= today.isoformat(),
            Show.show_date <= last_day,
        )
        .order_by(Show.show_date, Show.start_time)
    )
    grouped: dict[str, list[str]] = defaultdict(list)
    for show_date, start_time in rows:
        if session_has_started(show_date, start_time, offset):
            continue
        grouped[show_date].append(start_time)
    # A day whose screenings have all started is no longer a day to offer.
    return [{"date": day, "times": sorted(times)} for day, times in sorted(grouped.items()) if times]


async def seats_taken_by_others(
    session: AsyncSession, booking: Booking, session_time: str | None = None
) -> set[str]:
    """Seats of this booking that another live booking already occupies.

    Two situations need this. Cancelling frees the seats, so reviving a
    cancelled request is not a pure status flip. And moving a booking to the
    time the admin proposed lands it among a different set of neighbours.
    """
    seats = {seat for seat in booking.seats.split(",") if seat}
    if not seats:
        return set()
    rows = await session.scalars(
        select(Booking).where(
            Booking.movie_id == booking.movie_id,
            Booking.show_date == booking.show_date,
            Booking.session == (session_time or booking.session),
            Booking.status.in_(BLOCKING_STATUSES),
            Booking.id != booking.id,
        )
    )
    occupied = {seat for other in rows for seat in other.seats.split(",") if seat}
    return seats & occupied


def session_has_ended(
    show_date: str,
    start_time: str,
    duration_minutes: int,
    offset_minutes: int,
    now: datetime | None = None,
) -> bool:
    """True once the screening has finished in the cinema's own time.

    The server runs in UTC while the cinema does not, so the offset from the
    settings row is what makes this answer meaningful. The end is the start
    plus the film's running time — a viewer should not be able to review a
    film that is still playing.
    """
    try:
        start = datetime.fromisoformat(f"{show_date}T{start_time}")
    except ValueError:
        return False
    end = start + timedelta(minutes=max(duration_minutes, 0))
    local_now = (now or utcnow()).replace(tzinfo=None) + timedelta(minutes=offset_minutes)
    return local_now >= end
