from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.api.deps import current_user, get_db
from backend.models import AdminNotification, Booking, Favorite, Movie, User, UserNotification
from backend.schemas.booking import BookingProposalIn
from backend.schemas.profile import ProfileIn
from backend.services.catalog import serialize_booking, serialize_movie

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("")
async def profile(user: User = Depends(current_user), session: AsyncSession = Depends(get_db)) -> dict[str, object]:
    count = await session.scalar(select(func.count()).select_from(Booking).where(Booking.user_id == user.id)) or 0
    return {
        "first_name": user.first_name or user.name,
        "last_name": user.last_name,
        "phone": user.phone,
        "telegram_id": user.telegram_id,
        "created_at": user.created_at,
        "bookings": count,
    }


@router.patch("")
async def edit_profile(
    payload: ProfileIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    user.first_name = payload.first_name.strip()
    user.last_name = payload.last_name.strip()
    user.phone = payload.phone.strip()
    user.name = user.first_name
    await session.commit()
    return {"status": "updated"}


@router.get("/bookings")
async def profile_bookings(
    lang: str = "ru",
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, object]]:
    rows = await session.execute(
        select(Booking, Movie)
        .join(Movie, Booking.movie_id == Movie.id)
        .where(Booking.user_id == user.id)
        .order_by(Booking.id.desc())
    )
    return [serialize_booking(booking, movie, lang) for booking, movie in rows]


@router.get("/bookings/{booking_id}")
async def profile_booking(
    booking_id: int,
    lang: str = "ru",
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    rows = await session.execute(
        select(Booking, Movie)
        .join(Movie, Booking.movie_id == Movie.id)
        .where(Booking.id == booking_id, Booking.user_id == user.id)
    )
    item = rows.first()
    if item is None:
        raise HTTPException(404, "Booking not found")
    booking, movie = item
    return serialize_booking(booking, movie, lang)


@router.patch("/bookings/{booking_id}/proposal")
async def answer_booking_proposal(
    booking_id: int,
    payload: BookingProposalIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    booking = await session.scalar(
        select(Booking).where(Booking.id == booking_id, Booking.user_id == user.id)
    )
    if booking is None:
        raise HTTPException(404, "Booking not found")
    if not booking.proposed_session:
        raise HTTPException(409, "No proposed time")
    if payload.action == "accept":
        booking.session = booking.proposed_session
        booking.proposed_session = ""
        booking.admin_note = ""
        message = f"Клиент согласился на новое время заявки #{booking.id}: {booking.session}"
    else:
        booking.status = "cancelled"
        booking.admin_note = "Клиент отказался от предложенного времени"
        message = f"Клиент отказался от нового времени заявки #{booking.id}"
    session.add(AdminNotification(booking_id=booking.id, message=message))
    await session.commit()
    return {"status": booking.status, "session": booking.session}


@router.get("/favorites")
async def favorites(
    lang: str = "ru",
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, object]]:
    rows = await session.scalars(
        select(Movie)
        .options(selectinload(Movie.reviews))
        .join(Favorite, Favorite.movie_id == Movie.id)
        .where(Favorite.user_id == user.id, Movie.is_published.is_(True))
    )
    return [serialize_movie(item, language=lang) for item in rows]


@router.post("/favorites/{movie_id}")
async def add_favorite(
    movie_id: int,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    if await session.get(Movie, movie_id) is None:
        raise HTTPException(404, "Movie not found")
    exists = await session.scalar(
        select(Favorite).where(Favorite.user_id == user.id, Favorite.movie_id == movie_id)
    )
    if exists is None:
        session.add(Favorite(user_id=user.id, movie_id=movie_id))
        await session.commit()
    return {"status": "added"}


@router.delete("/favorites/{movie_id}")
async def remove_favorite(
    movie_id: int,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    item = await session.scalar(
        select(Favorite).where(Favorite.user_id == user.id, Favorite.movie_id == movie_id)
    )
    if item is not None:
        await session.delete(item)
        await session.commit()
    return {"status": "removed"}


@router.get("/notifications")
async def profile_notifications(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, object]]:
    rows = await session.scalars(
        select(UserNotification)
        .where(UserNotification.user_id == user.id)
        .order_by(UserNotification.id.desc())
    )
    return [
        {
            "id": item.id,
            "type": item.type,
            "title": item.title,
            "message": item.message,
            "is_read": item.is_read,
            "created_at": item.created_at,
        }
        for item in rows
    ]


@router.patch("/notifications/{notification_id}/read")
async def read_profile_notification(
    notification_id: int,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    item = await session.scalar(
        select(UserNotification).where(
            UserNotification.id == notification_id, UserNotification.user_id == user.id
        )
    )
    if item is None:
        raise HTTPException(404, "Notification not found")
    item.is_read = True
    await session.commit()
    return {"is_read": True}
