"""Admin dashboard, booking processing, notifications, settings and uploads."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import admin_required, get_db
from backend.core.config import BLOCKING_STATUSES, BOOKING_STATUSES
from backend.core.db import utcnow
from backend.models import AdminNotification, Booking, Movie, Show, User
from backend.schemas.booking import BookingDecisionIn, BookingStatusIn
from backend.schemas.settings import BasePriceIn, SettingsIn
from backend.services.booking import seats_taken_by_others
from backend.services.capacity import booking_party_size, reassign_booking_tokens
from backend.services.media import save_image_upload
from backend.services.settings import get_settings, serialize_settings_admin
from backend.services.telegram import (
    generic_booking_confirmed_message,
    send_telegram_message,
    user_booking_notification,
)

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(admin_required)])

#: Shown wherever a request has no film yet -- the mini app books the hall.
FALLBACK_TITLE = "Nova Cinema"


def _notification(item: AdminNotification) -> dict[str, object]:
    return {
        "id": item.id,
        "booking_id": item.booking_id,
        "message": item.message,
        "is_read": item.is_read,
        "created_at": item.created_at,
    }


@router.get("/bookings")
async def admin_bookings(session: AsyncSession = Depends(get_db)) -> list[dict[str, object]]:
    rows = await session.execute(
        select(Booking, Movie, User)
        # Outer: a generic request has no film until the admin agrees one, and
        # an inner join would simply hide every new booking from this screen.
        .outerjoin(Movie, Booking.movie_id == Movie.id)
        .join(User, Booking.user_id == User.id)
        .order_by(Booking.id.desc())
    )
    result: list[dict[str, object]] = []
    for booking, movie, user in rows:
        username = booking.telegram_username or user.username
        result.append(
            {
                "id": booking.id,
                "status": booking.status,
                "phone": booking.phone,
                "name": f"{booking.first_name} {booking.last_name}".strip(),
                "comment": booking.comment,
                "promo_code": booking.promo_code,
                "ticket_price": booking.ticket_price,
                "total": booking.total,
                "seats": booking.seats if movie is not None else "",
                "seats_count": booking_party_size(booking),
                "party_size": booking_party_size(booking),
                "created_at": booking.created_at,
                "telegram_id": user.telegram_id,
                "session": booking.session,
                "show_date": booking.show_date,
                "movie_id": movie.id if movie is not None else None,
                "movie": movie.title if movie is not None else FALLBACK_TITLE,
                "poster": movie.poster if movie is not None else "",
                "telegram_username": username,
                "chat_url": f"https://t.me/{username}" if username else None,
                "proposed_session": booking.proposed_session,
                "admin_note": booking.admin_note,
            }
        )
    return result


async def _refuse_if_the_hall_cannot_take_it(
    session: AsyncSession, booking: Booking, next_status: str
) -> None:
    """Block a status change that would put a request back into a full hall.

    Reviving a cancelled request is not a flag flip: the places it used to hold
    were released the moment it was cancelled, and somebody else may be sitting
    in them.  A generic booking is re-allocated fresh capacity tokens, because
    the numbers it carried mean nothing once they were given away.
    """
    if next_status not in BLOCKING_STATUSES or booking.status in BLOCKING_STATUSES:
        return
    if booking.movie_id is not None:
        clash = await seats_taken_by_others(session, booking)
        if clash:
            raise HTTPException(409, f"Seats already taken: {', '.join(sorted(clash))}")
    if not await reassign_booking_tokens(session, booking, booking.show_date, booking.session):
        raise HTTPException(409, "The hall is full at that time")


@router.patch("/bookings/{booking_id}/status")
async def update_booking_status(
    booking_id: int,
    payload: BookingStatusIn,
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    booking = await session.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(404, "Booking not found")
    await _refuse_if_the_hall_cannot_take_it(session, booking, payload.status)
    booking.status = payload.status
    if payload.status == "watched" and booking.completed_at is None:
        booking.completed_at = utcnow()
    session.add(
        user_booking_notification(
            booking, "Статус бронирования изменён", f"Заявка #{booking.id}: {payload.status}"
        )
    )
    await session.commit()
    return {"status": booking.status}


@router.patch("/bookings/{booking_id}/decision")
async def decide_booking(
    booking_id: int,
    payload: BookingDecisionIn,
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    row = await session.execute(
        select(Booking, User, Movie)
        .join(User, Booking.user_id == User.id)
        .outerjoin(Movie, Booking.movie_id == Movie.id)
        .where(Booking.id == booking_id)
    )
    item = row.first()
    if item is None:
        raise HTTPException(404, "Booking not found")
    booking, user, movie = item
    next_status = {"contact": "contacting", "confirm": "confirmed", "decline": "cancelled"}.get(payload.action)
    if next_status is not None:
        await _refuse_if_the_hall_cannot_take_it(session, booking, next_status)
    if payload.action == "contact":
        booking.status = "contacting"
        booking.admin_note = payload.reason.strip()
        message = f"Мы получили заявку #{booking.id} и свяжемся с вами для подтверждения."
    elif payload.action == "confirm":
        booking.status = "confirmed"
        booking.proposed_session = ""
        booking.admin_note = ""
        if movie is None:
            # Nothing was promised about a film, so the confirmation must not
            # imply one -- and it carries the contacts for arranging it.
            message = generic_booking_confirmed_message(booking, await get_settings(session))
        else:
            message = (
                f"Ваша бронь #{booking.id} подтверждена: {movie.title}, "
                f"{booking.show_date} {booking.session}."
            )
    elif payload.action == "decline":
        booking.status = "cancelled"
        booking.admin_note = payload.reason.strip()
        message = f"Заявка #{booking.id} отклонена. Причина: {booking.admin_note or 'не указана'}."
    else:
        if not payload.proposed_session:
            raise HTTPException(422, "Proposed time is required")
        booking.proposed_session = payload.proposed_session
        booking.admin_note = payload.reason.strip()
        message = (
            f"Nova Cinema предлагает другое время для заявки #{booking.id}: "
            f"{booking.proposed_session}. {booking.admin_note}"
        ).strip()
    session.add(user_booking_notification(booking, "Nova Cinema", message))
    await session.commit()
    await send_telegram_message(user.telegram_id, message)
    return {
        "status": booking.status,
        "proposed_session": booking.proposed_session,
        "admin_note": booking.admin_note,
    }


@router.get("/settings")
async def admin_settings(session: AsyncSession = Depends(get_db)) -> dict[str, object]:
    return serialize_settings_admin(await get_settings(session))


@router.put("/settings")
async def update_settings(payload: SettingsIn, session: AsyncSession = Depends(get_db)) -> dict[str, object]:
    settings = await get_settings(session)
    for key, value in payload.model_dump().items():
        setattr(settings, key, value)
    await session.commit()
    await session.refresh(settings)
    return serialize_settings_admin(settings)


@router.patch("/settings/base-price")
async def update_base_price(payload: BasePriceIn, session: AsyncSession = Depends(get_db)) -> dict[str, int]:
    """Kept as the quick price control; the full form is PUT /api/admin/settings."""
    settings = await get_settings(session)
    settings.base_ticket_price = payload.base_ticket_price
    await session.commit()
    return {"base_ticket_price": payload.base_ticket_price}


@router.get("/notifications")
async def admin_notifications(session: AsyncSession = Depends(get_db)) -> list[dict[str, object]]:
    rows = await session.scalars(select(AdminNotification).order_by(AdminNotification.id.desc()))
    return [_notification(item) for item in rows]


@router.patch("/notifications/{notification_id}/read")
async def read_notification(notification_id: int, session: AsyncSession = Depends(get_db)) -> dict[str, bool]:
    item = await session.get(AdminNotification, notification_id)
    if item is None:
        raise HTTPException(404, "Notification not found")
    item.is_read = True
    await session.commit()
    return {"is_read": True}


@router.get("/dashboard")
async def dashboard(session: AsyncSession = Depends(get_db)) -> dict[str, object]:
    movie_count = await session.scalar(select(func.count()).select_from(Movie)) or 0
    booking_count = await session.scalar(select(func.count()).select_from(Booking)) or 0
    status_rows = await session.execute(select(Booking.status, func.count()).group_by(Booking.status))
    counts = {value: 0 for value in BOOKING_STATUSES}
    counts.update({status_name: count for status_name, count in status_rows})
    notices = list(await session.scalars(select(AdminNotification).order_by(AdminNotification.id.desc()).limit(5)))
    recent = list(await session.scalars(select(Booking).order_by(Booking.id.desc()).limit(5)))
    return {
        "movies": movie_count,
        # No `active_sessions`: it counted rows in the movie-bound `shows` table,
        # which the booking flow no longer writes to, so the tile sat at zero
        # forever and told the administrator something untrue.
        "bookings": booking_count,
        "statuses": counts,
        "recent_bookings": [
            {
                "id": item.id,
                "name": f"{item.first_name} {item.last_name}".strip(),
                "phone": item.phone,
                "status": item.status,
                "total": item.total,
            }
            for item in recent
        ],
        "notifications": [_notification(item) for item in notices],
    }


@router.post("/uploads")
async def upload_image(file: UploadFile = File(...)) -> dict[str, str]:
    return {"url": await save_image_upload(file)}
