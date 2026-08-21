"""Ticket price resolution: show override -> movie price -> admin base price."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Movie, Show
from backend.services.settings import get_settings


async def base_price(session: AsyncSession) -> int:
    settings = await get_settings(session)
    return settings.base_ticket_price


async def ticket_price(session: AsyncSession, movie_id: int, show_date: str, start_time: str) -> int:
    """Price for one seat at a given screening, at this moment in time.

    Callers that persist a booking must freeze the returned value on the row --
    a later price change must not rewrite existing bookings.
    """
    show_price = await session.scalar(
        select(Show.ticket_price).where(
            Show.movie_id == movie_id,
            Show.show_date == show_date,
            Show.start_time == start_time,
            Show.status == "active",
        )
    )
    if show_price and show_price > 0:
        return show_price
    movie_price = await session.scalar(select(Movie.ticket_price).where(Movie.id == movie_id))
    if movie_price and movie_price > 0:
        return movie_price
    return await base_price(session)
