from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.exc import StaleDataError

from backend.api.deps import current_user, get_db
from backend.core.db import utcnow
from backend.models import AdminNotification, Booking, Favorite, Movie, User, UserNotification
from backend.schemas.booking import BookingProposalIn
from backend.schemas.profile import ProfileIn
from backend.services.booking_decisions import (
    BookingNotFound,
    BookingTransitionConflict,
    HallIsFull,
    ProposalNotFound,
    SeatsAlreadyTaken,
    answer_proposal,
)
from backend.services.catalog import serialize_booking, serialize_movie
from backend.services.booking import session_has_started
from backend.services.capacity import booking_party_size
from backend.services.settings import get_settings
from backend.services.retention import hide_viewer_history, prune_viewer_records
from backend.services.telegram import notify_admins

router = APIRouter(prefix="/api/profile", tags=["profile"])
CANCELLABLE_STATUSES = {"pending", "contacting", "confirmed"}


@router.get("")
async def profile(user: User = Depends(current_user), session: AsyncSession = Depends(get_db)) -> dict[str, object]:
    await prune_viewer_records(session, user.id)
    count = await session.scalar(
        select(func.count()).select_from(Booking).where(
            Booking.user_id == user.id, Booking.viewer_hidden_at.is_(None)
        )
    ) or 0
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
    await prune_viewer_records(session, user.id)
    rows = await session.execute(
        select(Booking, Movie)
        # Outer: a generic request carries no film, and an inner join would drop
        # every new booking out of the viewer's own history.
        .outerjoin(Movie, Booking.movie_id == Movie.id)
        .where(Booking.user_id == user.id, Booking.viewer_hidden_at.is_(None))
        .order_by(Booking.id.desc())
    )
    return [serialize_booking(booking, movie, lang) for booking, movie in rows]


@router.delete("/history/bookings")
async def clear_profile_booking_history(
    user: User = Depends(current_user), session: AsyncSession = Depends(get_db)
) -> dict[str, int]:
    return {"cleared": await hide_viewer_history(session, user.id)}


@router.get("/bookings/{booking_id}")
async def profile_booking(
    booking_id: int,
    lang: str = "ru",
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    rows = await session.execute(
        select(Booking, Movie)
        .outerjoin(Movie, Booking.movie_id == Movie.id)
        .where(
            Booking.id == booking_id,
            Booking.user_id == user.id,
            Booking.viewer_hidden_at.is_(None),
        )
    )
    item = rows.first()
    if item is None:
        raise HTTPException(404, "Booking not found")
    booking, movie = item
    return serialize_booking(booking, movie, lang)


@router.patch("/bookings/{booking_id}/cancel")
async def cancel_profile_booking(
    booking_id: int,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Cancel the caller's own active booking while retaining an audit/history row."""
    booking = await session.scalar(
        select(Booking)
        .where(Booking.id == booking_id, Booking.user_id == user.id)
        .with_for_update()
    )
    if booking is None:
        # Ownership is deliberately indistinguishable from a missing id.
        raise HTTPException(404, "Booking not found")
    if booking.status == "cancelled":
        return {"status": "cancelled"}
    if booking.status not in CANCELLABLE_STATUSES:
        raise HTTPException(409, "Booking can no longer be cancelled")

    settings = await get_settings(session)
    if session_has_started(
        booking.show_date, booking.session, settings.timezone_offset_minutes
    ):
        raise HTTPException(409, "Session has already started")

    booking.status = "cancelled"
    booking.completed_at = utcnow()
    booking.proposed_session = ""
    booking.admin_note = "Отменено клиентом"
    message = (
        f"Клиент отменил бронь #{booking.id}: {booking.show_date} {booking.session}, "
        f"гостей: {booking_party_size(booking)}"
    )
    owner_id = user.id
    session.add(AdminNotification(booking_id=booking.id, message=message))
    try:
        await session.commit()
    except StaleDataError:
        await session.rollback()
        current = await session.scalar(
            select(Booking).where(Booking.id == booking_id, Booking.user_id == owner_id)
        )
        if current is not None and current.status == "cancelled":
            return {"status": "cancelled"}
        raise HTTPException(409, "Booking changed; refresh and try again")
    # The cancellation is already durable if Telegram is temporarily unavailable.
    await notify_admins(message)
    return {"status": "cancelled"}


@router.patch("/bookings/{booking_id}/proposal")
async def answer_booking_proposal(
    booking_id: int,
    payload: BookingProposalIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Shares `answer_proposal` with the bot's own Accept/Decline buttons, so
    the viewer gets the identical outcome whichever surface they answer from.
    """
    action = "accept" if payload.action == "accept" else "decline"
    try:
        result = await answer_proposal(session, booking_id, user.telegram_id, action)
    except (BookingNotFound, ProposalNotFound):
        raise HTTPException(404, "Booking not found")
    except HallIsFull:
        raise HTTPException(409, "The hall is full at that time")
    except SeatsAlreadyTaken as error:
        raise HTTPException(409, str(error))
    except BookingTransitionConflict:
        raise HTTPException(409, "Booking changed; refresh and try again")
    # Same rule as on a new booking: the panel keeps the row, Telegram gets a
    # live copy, and a failure to deliver it never touches the answer above.
    await notify_admins(result.admin_message)
    return {"status": result.status, "session": result.session_time}


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
    await prune_viewer_records(session, user.id)
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


@router.delete("/notifications")
async def clear_profile_notifications(
    user: User = Depends(current_user), session: AsyncSession = Depends(get_db)
) -> dict[str, int]:
    result = await session.execute(
        delete(UserNotification).where(UserNotification.user_id == user.id)
    )
    await session.commit()
    return {"cleared": result.rowcount or 0}


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
