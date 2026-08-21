"""Admin management of the movie catalog and the screening schedule."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.api.deps import admin_required, get_db
from backend.models import Booking, Movie, Show
from backend.schemas.movie import MovieIn, MovieLookupIn
from backend.schemas.show import ShowBulkIn, ShowIn
from backend.services.booking import show_times_by_movie
from backend.services.catalog import serialize_movie
from backend.services.i18n import localize_movie_payload
from backend.services.pricing import base_price
from backend.services.tmdb import lookup_movie_payload

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(admin_required)])

MAX_BULK_DAYS = 60


@router.get("/movies")
async def admin_movies(lang: str = "ru", session: AsyncSession = Depends(get_db)) -> list[dict[str, object]]:
    result = await session.scalars(
        select(Movie).options(selectinload(Movie.reviews)).order_by(Movie.sort_order, Movie.id)
    )
    items = list(result)
    times = await show_times_by_movie(session, [movie.id for movie in items])
    return [serialize_movie(movie, language=lang, sessions=times.get(movie.id, [])) for movie in items]


@router.post("/movies/lookup")
async def lookup_movie(payload: MovieLookupIn) -> dict[str, object]:
    return await lookup_movie_payload(payload.title)


@router.post("/movies")
async def create_movie(payload: MovieIn, session: AsyncSession = Depends(get_db)) -> dict[str, object]:
    values, warning = await localize_movie_payload(payload)
    item = Movie(**values)
    session.add(item)
    await session.commit()
    return {"id": item.id, "translation_warning": warning}


@router.patch("/movies/{movie_id}")
async def edit_movie(movie_id: int, payload: MovieIn, session: AsyncSession = Depends(get_db)) -> dict[str, object]:
    item = await session.get(Movie, movie_id)
    if item is None:
        raise HTTPException(404, "Movie not found")
    values, warning = await localize_movie_payload(payload)
    for key, value in values.items():
        setattr(item, key, value)
    await session.commit()
    return {"status": "updated", "translation_warning": warning}


@router.delete("/movies/{movie_id}")
async def delete_movie(movie_id: int, session: AsyncSession = Depends(get_db)) -> dict[str, str]:
    item = await session.get(Movie, movie_id)
    if item is None:
        raise HTTPException(404, "Movie not found")
    booked = await session.scalar(select(Booking.id).where(Booking.movie_id == movie_id).limit(1))
    if booked is not None:
        raise HTTPException(409, "Movie has bookings")
    await session.execute(Show.__table__.delete().where(Show.movie_id == movie_id))
    await session.delete(item)
    await session.commit()
    return {"status": "deleted"}


def _serialize_show(show: Show, movie: Movie, base: int) -> dict[str, object]:
    return {
        "id": show.id,
        "movie_id": show.movie_id,
        "movie": movie.title,
        "show_date": show.show_date,
        "start_time": show.start_time,
        # Kept for the current admin UI, which still reads `session`.
        "session": show.start_time,
        "ticket_price": show.ticket_price,
        "resolved_price": show.ticket_price or movie.ticket_price or base,
        "status": show.status,
    }


@router.get("/sessions")
async def admin_sessions(session: AsyncSession = Depends(get_db)) -> list[dict[str, object]]:
    base = await base_price(session)
    rows = await session.execute(
        select(Show, Movie)
        .join(Movie, Show.movie_id == Movie.id)
        .order_by(Show.show_date.desc(), Show.start_time)
    )
    return [_serialize_show(show, movie, base) for show, movie in rows]


@router.post("/sessions")
async def create_session(payload: ShowIn, session: AsyncSession = Depends(get_db)) -> dict[str, int]:
    if await session.get(Movie, payload.movie_id) is None:
        raise HTTPException(404, "Movie not found")
    duplicate = await session.scalar(
        select(Show.id).where(
            Show.movie_id == payload.movie_id,
            Show.show_date == payload.show_date,
            Show.start_time == payload.start_time,
        )
    )
    if duplicate is not None:
        raise HTTPException(409, "Session already exists")
    item = Show(**payload.model_dump())
    session.add(item)
    await session.commit()
    return {"id": item.id}


@router.post("/sessions/bulk")
async def create_sessions_bulk(payload: ShowBulkIn, session: AsyncSession = Depends(get_db)) -> dict[str, int]:
    """Fill a date range with the same daily times — the common scheduling case."""
    if await session.get(Movie, payload.movie_id) is None:
        raise HTTPException(404, "Movie not found")
    start = date.fromisoformat(payload.date_from)
    end = date.fromisoformat(payload.date_to)
    if end < start:
        raise HTTPException(422, "date_to must not be earlier than date_from")
    if (end - start).days + 1 > MAX_BULK_DAYS:
        raise HTTPException(422, f"Range is limited to {MAX_BULK_DAYS} days")

    existing = {
        (row.show_date, row.start_time)
        for row in await session.execute(
            select(Show.show_date, Show.start_time).where(
                Show.movie_id == payload.movie_id,
                Show.show_date >= payload.date_from,
                Show.show_date <= payload.date_to,
            )
        )
    }
    created = 0
    for offset in range((end - start).days + 1):
        show_date = (start + timedelta(days=offset)).isoformat()
        for start_time in sorted(set(payload.times)):
            if (show_date, start_time) in existing:
                continue
            session.add(
                Show(
                    movie_id=payload.movie_id,
                    show_date=show_date,
                    start_time=start_time,
                    ticket_price=payload.ticket_price,
                )
            )
            created += 1
    await session.commit()
    return {"created": created}


@router.patch("/sessions/{show_id}")
async def edit_session(show_id: int, payload: ShowIn, session: AsyncSession = Depends(get_db)) -> dict[str, str]:
    item = await session.get(Show, show_id)
    if item is None:
        raise HTTPException(404, "Session not found")
    if await session.get(Movie, payload.movie_id) is None:
        raise HTTPException(404, "Movie not found")
    duplicate = await session.scalar(
        select(Show.id).where(
            Show.movie_id == payload.movie_id,
            Show.show_date == payload.show_date,
            Show.start_time == payload.start_time,
            Show.id != show_id,
        )
    )
    if duplicate is not None:
        raise HTTPException(409, "Session already exists")
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    await session.commit()
    return {"status": "updated"}


@router.delete("/sessions/{show_id}")
async def delete_session(show_id: int, session: AsyncSession = Depends(get_db)) -> dict[str, str]:
    item = await session.get(Show, show_id)
    if item is None:
        raise HTTPException(404, "Session not found")
    booked = await session.scalar(
        select(Booking.id)
        .where(
            Booking.movie_id == item.movie_id,
            Booking.show_date == item.show_date,
            Booking.session == item.start_time,
            Booking.status != "cancelled",
        )
        .limit(1)
    )
    if booked is not None:
        raise HTTPException(409, "Session has bookings")
    await session.delete(item)
    await session.commit()
    return {"status": "deleted"}
