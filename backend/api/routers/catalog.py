from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.api.deps import current_user, get_db
from backend.models import Booking, Movie, Review, User
from backend.schemas.movie import ReviewIn
from backend.services.booking import show_times_by_movie, upcoming_show_times
from backend.services.catalog import serialize_movie

router = APIRouter(prefix="/api/movies", tags=["catalog"])


@router.get("")
async def movies(lang: str = "ru", session: AsyncSession = Depends(get_db)) -> list[dict[str, object]]:
    result = await session.scalars(
        select(Movie)
        .options(selectinload(Movie.reviews))
        .where(Movie.is_published.is_(True))
        .order_by(Movie.sort_order, Movie.id)
    )
    items = list(result)
    times = await show_times_by_movie(session, [movie.id for movie in items])
    return [serialize_movie(movie, language=lang, sessions=times.get(movie.id, [])) for movie in items]


@router.get("/{movie_id}")
async def movie_detail(movie_id: int, lang: str = "ru", session: AsyncSession = Depends(get_db)) -> dict[str, object]:
    movie = await session.scalar(select(Movie).options(selectinload(Movie.reviews)).where(Movie.id == movie_id))
    if movie is None or not movie.is_published:
        raise HTTPException(404, "Movie not found")
    times = await show_times_by_movie(session, [movie.id])
    data = serialize_movie(movie, language=lang, sessions=times.get(movie.id, []))
    data["reviews"] = [
        {"rating": review.rating, "text": review.text, "created_at": review.created_at, "user_name": "Зритель"}
        for review in movie.reviews
        if review.approved
    ]
    similar = await session.scalars(
        select(Movie)
        .where(Movie.id != movie_id, Movie.is_published.is_(True))
        .order_by(Movie.sort_order, Movie.id)
        .limit(2)
    )
    similar_items = list(similar)
    similar_times = await show_times_by_movie(session, [item.id for item in similar_items])
    data["similar_movies"] = [
        serialize_movie(item, [], lang, similar_times.get(item.id, [])) for item in similar_items
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
    seen = await session.scalar(
        select(Booking.id).where(
            Booking.user_id == user.id,
            Booking.movie_id == movie_id,
            Booking.status == "watched",
        )
    )
    if seen is None:
        raise HTTPException(403, "Review is available after viewing")
    session.add(Review(movie_id=movie_id, user_id=user.id, rating=payload.rating, text=payload.text.strip()))
    await session.commit()
    return {"status": "published"}
