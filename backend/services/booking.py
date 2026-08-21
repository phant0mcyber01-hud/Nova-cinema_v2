"""Screening lookup and booking-side rules shared by the public endpoints."""
from __future__ import annotations

from collections import defaultdict
from datetime import date as date_type, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import BLOCKING_STATUSES
from backend.models import Movie, Show

__all__ = [
    "BLOCKING_STATUSES",
    "ensure_show",
    "movie_schedule",
    "show_times_by_movie",
    "upcoming_show_times",
]


async def ensure_show(session: AsyncSession, movie_id: int, show_date: str, start_time: str) -> Show:
    """Reject anything that is not a published movie on an active screening.

    Replaces the old check that accepted any well-formed HH:MM, so the schedule
    is now genuinely controlled from the admin panel.
    """
    movie = await session.get(Movie, movie_id)
    if movie is None or not movie.is_published:
        raise HTTPException(404, "Movie not found")
    # A screening that has already been and gone must not be bookable, even
    # though the admin may keep the row for reporting.  Dates are ISO strings,
    # so a plain comparison is enough.
    if show_date < date_type.today().isoformat():
        raise HTTPException(404, "Session not found")
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
    if show_date < date_type.today().isoformat():
        return []
    rows = await session.scalars(
        select(Show.start_time)
        .where(Show.movie_id == movie_id, Show.show_date == show_date, Show.status == "active")
        .order_by(Show.start_time)
    )
    return list(rows)


async def show_times_by_movie(
    session: AsyncSession, movie_ids: list[int], show_date: str | None = None
) -> dict[int, list[str]]:
    """One query for the whole catalog instead of a query per movie."""
    if not movie_ids:
        return {}
    query = select(Show.movie_id, Show.start_time).where(
        Show.movie_id.in_(movie_ids), Show.status == "active"
    )
    if show_date is not None:
        query = query.where(Show.show_date == show_date)
    grouped: dict[int, set[str]] = defaultdict(set)
    for movie_id, start_time in await session.execute(query):
        grouped[movie_id].add(start_time)
    return {movie_id: sorted(times) for movie_id, times in grouped.items()}


async def movie_schedule(session: AsyncSession, movie_id: int, days: int) -> list[dict[str, object]]:
    """Upcoming screenings grouped by date, for the movie card.

    Past dates are skipped and the window matches the admin-configured
    `booking_days_ahead`, so the card never offers a slot that cannot be booked.
    """
    today = date_type.today()
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
        grouped[show_date].append(start_time)
    return [{"date": day, "times": sorted(times)} for day, times in sorted(grouped.items())]
