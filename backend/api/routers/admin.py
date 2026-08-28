"""Admin dashboard, booking processing, notifications, settings and uploads."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import admin_required, get_db
from backend.core.config import BOOKING_STATUSES
from backend.models import AdminNotification, Booking, Movie, User
from backend.schemas.booking import BookingDecisionIn, BookingStatusIn
from backend.schemas.settings import BasePriceIn, SettingsIn
from backend.services.booking_decisions import (
    BookingNotFound,
    BookingTransitionConflict,
    HallIsFull,
    ProposedTimeRequired,
    SeatsAlreadyTaken,
    apply_decision,
    apply_status,
)
from backend.services.capacity import booking_party_size
from backend.services.media import save_image_upload
from backend.services.settings import get_settings, serialize_settings_admin
from backend.services.retention import prune_admin_records
from backend.services.telegram import send_telegram_message, viewer_proposal_keyboard

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


@router.patch("/bookings/{booking_id}/status")
async def update_booking_status(
    booking_id: int,
    payload: BookingStatusIn,
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """The blunt panel action: set a status directly (`watched` and manual overrides).

    Shares `apply_status` with the bot's own callback handler, so a booking
    processed from either surface obeys exactly the same hall-capacity rule.
    """
    try:
        result = await apply_status(session, booking_id, payload.status)
    except BookingNotFound:
        raise HTTPException(404, "Booking not found")
    except HallIsFull:
        raise HTTPException(409, "The hall is full at that time")
    except SeatsAlreadyTaken as error:
        raise HTTPException(409, str(error))
    except BookingTransitionConflict:
        raise HTTPException(409, "Booking changed; refresh and try again")
    return {"status": result.status}


@router.patch("/bookings/{booking_id}/decision")
async def decide_booking(
    booking_id: int,
    payload: BookingDecisionIn,
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """`contact`/`confirm`/`decline`/`propose` -- the same actions the bot's inline
    buttons trigger, run through the shared `apply_decision`.
    """
    try:
        result = await apply_decision(
            session, booking_id, payload.action,
            reason=payload.reason, proposed_session=payload.proposed_session,
        )
    except BookingNotFound:
        raise HTTPException(404, "Booking not found")
    except HallIsFull:
        raise HTTPException(409, "The hall is full at that time")
    except SeatsAlreadyTaken as error:
        raise HTTPException(409, str(error))
    except ProposedTimeRequired:
        raise HTTPException(422, "Proposed time is required")
    except BookingTransitionConflict:
        raise HTTPException(409, "Booking changed; refresh and try again")

    # A proposed time needs an answer, not just a notification: the viewer
    # gets Accept/Decline buttons right in the same message.
    keyboard = viewer_proposal_keyboard(booking_id) if payload.action == "propose" else None
    await send_telegram_message(result.viewer_telegram_id, result.viewer_message, reply_markup=keyboard)
    return {
        "status": result.status,
        "proposed_session": result.proposed_session,
        "admin_note": result.admin_note,
    }


@router.get("/settings")
async def admin_settings(session: AsyncSession = Depends(get_db)) -> dict[str, object]:
    return serialize_settings_admin(await get_settings(session))


@router.put("/settings")
async def update_settings(payload: SettingsIn, session: AsyncSession = Depends(get_db)) -> dict[str, object]:
    settings = await get_settings(session)
    for key, value in payload.model_dump().items():
        if key == "faq":
            # The column is a plain JSON string, same pattern as a movie's
            # cast/gallery: nothing here queries inside the FAQ list, so a
            # dedicated table would only add joins nothing reads from.
            settings.faq_json = json.dumps(value, ensure_ascii=False)
        else:
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
    await prune_admin_records(session)
    rows = await session.scalars(select(AdminNotification).order_by(AdminNotification.id.desc()))
    return [_notification(item) for item in rows]


@router.delete("/notifications")
async def clear_admin_notifications(session: AsyncSession = Depends(get_db)) -> dict[str, int]:
    result = await session.execute(delete(AdminNotification))
    await session.commit()
    return {"cleared": result.rowcount or 0}


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
    await prune_admin_records(session)
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

