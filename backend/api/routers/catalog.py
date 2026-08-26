from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.api.deps import current_user, get_db
from backend.core.config import DATE_PATTERN
from backend.core.security import optional_user
from backend.models import Movie, Review, Show, User
from backend.schemas.movie import ReviewIn
from backend.services.booking import cinema_now, movie_schedule, show_times_by_movie, upcoming_show_times
from backend.services.catalog import matches_query, serialize_movie, split_genres
from backend.services.deep_link import share_link
from backend.services.settings import get_settings

router = APIRouter(prefix="/api/movies", tags=["catalog"])


@router.get("")
async def movies(
    lang: str = "ru",
    date: str | None = None,
    q: str = Query(default="", max_length=100),
    only_new: bool = False,
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, object]]:
    """Published catalog.

    `date` narrows the list to movies with an active screening that day, and each
    `sessions` array then holds that day's times only. `q` searches title, genre,
    description, country, director, cast and year in the requested language.
    `only_new` keeps just the current new releases.
    """
    if date is not None and not re.fullmatch(DATE_PATTERN, date):
        raise HTTPException(422, "Invalid date")
    query = (
        select(Movie)
        .options(selectinload(Movie.reviews))
        .where(Movie.is_published.is_(True))
        .order_by(Movie.sort_order, Movie.id)
    )
    if date is not None:
        query = query.where(
            Movie.id.in_(
                select(Show.movie_id).where(Show.show_date == date, Show.status == "active")
            )
        )
    items = list(await session.scalars(query))
    times = await show_times_by_movie(session, [movie.id for movie in items], date, upcoming_only=True)
    today = cinema_now((await get_settings(session)).timezone_offset_minutes).date().isoformat()
    result = [
        serialize_movie(movie, language=lang, sessions=times.get(movie.id, []), today=today)
        for movie in items
    ]
    if only_new:
        # is_new in the payload already accounts for new_until expiry.
        result = [item for item in result if item["is_new"]]
    if q.strip():
        result = [item for item in result if matches_query(item, q)]
    return result


@router.get("/{movie_id}")
async def movie_detail(
    movie_id: int,
    lang: str = "ru",
    user: User | None = Depends(optional_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    movie = await session.scalar(select(Movie).options(selectinload(Movie.reviews)).where(Movie.id == movie_id))
    if movie is None or not movie.is_published:
        raise HTTPException(404, "Movie not found")
    times = await show_times_by_movie(session, [movie.id], upcoming_only=True)
    settings = await get_settings(session)
    today = cinema_now(settings.timezone_offset_minutes).date().isoformat()
    data = serialize_movie(movie, language=lang, sessions=times.get(movie.id, []), today=today)
    data["schedule"] = await movie_schedule(session, movie_id, settings.booking_days_ahead)
    data["share_link"] = share_link(settings.bot_username, movie_id)
    already_reviewed = user is not None and (
        await session.scalar(
            select(Review.id).where(Review.user_id == user.id, Review.movie_id == movie_id)
        )
    ) is not None
    # Signed in is the whole requirement: a booking no longer names a film (it
    # reserves the hall for a date and time, and which film is shown is agreed
    # with the administrator afterwards), so gating on "watched this film" was
    # a rule nobody could ever satisfy. One review per viewer per movie and
    # admin moderation (Review.approved) are still the real safeguards.
    data["can_review"] = user is not None and not already_reviewed
    data["has_reviewed"] = already_reviewed
    data["reviews"] = [
        {"rating": review.rating, "text": review.text, "created_at": review.created_at, "user_name": "Зритель"}
        for review in movie.reviews
        if review.approved
    ]
    # "Похожие" has to mean something: films are ranked by how many genres they
    # share with this one, so a horror film is never followed by a cartoon.
    # A film with several genres ("Фантастика, Боевик") matches on either.
    wanted = set(split_genres(movie.genre))
    candidates = list(
        await session.scalars(
            select(Movie)
            .where(Movie.id != movie_id, Movie.is_published.is_(True))
            .order_by(Movie.sort_order, Movie.id)
        )
    )
    scored = [
        (len(wanted & set(split_genres(item.genre))), index, item)
        for index, item in enumerate(candidates)
    ]
    # Only films that genuinely share a genre. An empty block is honest; a
    # cartoon recommended under a horror film is what the client complained
    # about, and the UI already hides the section when there is nothing in it.
    scored = [row for row in scored if row[0] > 0]
    scored.sort(key=lambda row: (-row[0], row[1]))
    similar_items = [item for _, _, item in scored[:2]]
    similar_times = await show_times_by_movie(session, [item.id for item in similar_items], upcoming_only=True)
    data["similar_movies"] = [
        serialize_movie(item, [], lang, similar_times.get(item.id, []), today) for item in similar_items
    ]
    return data


@router.get("/{movie_id}/sessions")
async def movie_sessions(movie_id: int, show_date: str, session: AsyncSession = Depends(get_db)) -> dict[str, object]:
    movie = await session.get(Movie, movie_id)
    if movie is None or not movie.is_published:
        raise HTTPException(404, "Movie not found")
    return {
        "movie_id": movie_id,
        "show_date": show_date,
        "sessions": await upcoming_show_times(session, movie_id, show_date),
    }


@router.post("/{movie_id}/reviews")
async def create_review(
    movie_id: int,
    payload: ReviewIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    already = await session.scalar(
        select(Review.id).where(Review.user_id == user.id, Review.movie_id == movie_id)
    )
    if already is not None:
        raise HTTPException(409, "You have already reviewed this movie")
    session.add(Review(movie_id=movie_id, user_id=user.id, rating=payload.rating, text=payload.text.strip()))
    await session.commit()
    return {"status": "published"}
