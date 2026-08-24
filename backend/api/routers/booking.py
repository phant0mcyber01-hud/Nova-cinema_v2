from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import current_user, get_db
from backend.core.config import AWAITING_STATUSES, BLOCKING_STATUSES, CONFIRMED_STATUSES
from backend.core.security import optional_user
from backend.core.db import utcnow
from backend.models import AdminNotification, Booking, Movie, SeatHold, User
from backend.schemas.booking import BookingConfirmIn, HoldIn
from backend.services.booking import ensure_bookable_slot
from backend.services.hall import valid_seat
from backend.services.pricing import ticket_price
from backend.services.settings import get_settings
from backend.services.telegram import new_booking_admin_message, notify_admins

router = APIRouter(tags=["booking"])


async def _booked_seats(
    session: AsyncSession, movie_id: int, show_date: str, session_time: str, statuses: tuple[str, ...]
) -> set[str]:
    bookings = await session.scalars(
        select(Booking).where(
            Booking.movie_id == movie_id,
            Booking.show_date == show_date,
            Booking.session == session_time,
            Booking.status.in_(statuses),
        )
    )
    return {seat for booking in bookings for seat in booking.seats.split(",") if seat}


async def _taken_seats(session: AsyncSession, movie_id: int, show_date: str, session_time: str) -> set[str]:
    return await _booked_seats(session, movie_id, show_date, session_time, BLOCKING_STATUSES)


@router.get("/api/sessions/{movie_id}/seats")
async def session_seats(
    movie_id: int,
    show_date: str,
    session_time: str,
    user: User | None = Depends(optional_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Hall layout with a seat state the client can render directly.

    Four states, as the spec asks: free (in none of the lists), selected (the
    client's own doing), awaiting confirmation, and booked. A live hold by
    somebody else counts as awaiting — the seat is being taken right now.
    """
    await ensure_bookable_slot(session, movie_id, show_date, session_time)
    settings = await get_settings(session)
    await session.execute(SeatHold.__table__.delete().where(SeatHold.expires_at < utcnow()))
    await session.commit()

    holds = list(
        await session.scalars(
            select(SeatHold).where(
                SeatHold.movie_id == movie_id,
                SeatHold.show_date == show_date,
                SeatHold.session == session_time,
            )
        )
    )
    mine = {hold.seat for hold in holds if user is not None and hold.user_id == user.id}
    others_holding = {hold.seat for hold in holds} - mine

    booked = await _booked_seats(session, movie_id, show_date, session_time, CONFIRMED_STATUSES)
    awaiting = await _booked_seats(session, movie_id, show_date, session_time, AWAITING_STATUSES)
    awaiting |= others_holding

    return {
        "rows": settings.hall_rows,
        "cols": settings.hall_cols,
        "seats_count": settings.hall_seats,
        "max_seats": settings.max_seats_per_booking,
        "price": await ticket_price(session, movie_id, show_date, session_time),
        "currency": settings.currency,
        "hold_minutes": settings.hold_minutes,
        "booked": sorted(booked),
        "awaiting": sorted(awaiting),
        "mine": sorted(mine),
        # Union of everything the viewer cannot pick, kept as the simple check.
        "taken": sorted(booked | awaiting),
    }


@router.post("/api/holds")
async def hold_seats(
    payload: HoldIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    await ensure_bookable_slot(session, payload.movie_id, payload.show_date, payload.session)
    settings = await get_settings(session)
    if len(payload.seats) > settings.max_seats_per_booking:
        raise HTTPException(422, f"Maximum {settings.max_seats_per_booking} seats per booking")
    if len(set(payload.seats)) != len(payload.seats) or not all(
        valid_seat(seat, settings.hall_rows, settings.hall_cols) for seat in payload.seats
    ):
        raise HTTPException(422, "Invalid seats")

    now = utcnow()
    await session.execute(SeatHold.__table__.delete().where(SeatHold.expires_at < now))
    existing = await session.scalars(
        select(SeatHold)
        .where(
            SeatHold.movie_id == payload.movie_id,
            SeatHold.show_date == payload.show_date,
            SeatHold.session == payload.session,
            SeatHold.seat.in_(payload.seats),
            SeatHold.user_id != user.id,
        )
        .with_for_update()
    )
    if list(existing):
        raise HTTPException(409, "Seat is temporarily held")
    if set(payload.seats) & await _taken_seats(session, payload.movie_id, payload.show_date, payload.session):
        raise HTTPException(409, "Seat is already booked")

    await session.execute(
        SeatHold.__table__.delete().where(
            SeatHold.movie_id == payload.movie_id,
            SeatHold.show_date == payload.show_date,
            SeatHold.session == payload.session,
            SeatHold.user_id == user.id,
        )
    )
    expires = now + timedelta(minutes=settings.hold_minutes)
    session.add_all(
        [
            SeatHold(
                movie_id=payload.movie_id,
                show_date=payload.show_date,
                session=payload.session,
                seat=seat,
                user_id=user.id,
                expires_at=expires,
            )
            for seat in payload.seats
        ]
    )
    try:
        await session.commit()
    except IntegrityError:
        # uq_seat_hold fired: somebody claimed the same seat between the check
        # above and this insert. The database is the arbiter, not the check.
        await session.rollback()
        raise HTTPException(409, "Seat is temporarily held") from None
    price = await ticket_price(session, payload.movie_id, payload.show_date, payload.session)
    return {
        "expires_at": expires,
        "seats": payload.seats,
        "ticket_price": price,
        "total": len(payload.seats) * price,
    }


@router.delete("/api/holds")
async def release_seats(
    movie_id: int,
    show_date: str,
    session_time: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Drop the caller's hold when they clear their selection or walk away.

    Without this a seat stays blocked for the whole hold window even though
    nobody is going to take it.
    """
    await session.execute(
        SeatHold.__table__.delete().where(
            SeatHold.movie_id == movie_id,
            SeatHold.show_date == show_date,
            SeatHold.session == session_time,
            SeatHold.user_id == user.id,
        )
    )
    await session.commit()
    return {"status": "released"}


@router.post("/api/bookings/confirm")
async def confirm_booking(
    payload: BookingConfirmIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    await ensure_bookable_slot(session, payload.movie_id, payload.show_date, payload.session)
    holds = await session.scalars(
        select(SeatHold)
        .where(
            SeatHold.movie_id == payload.movie_id,
            SeatHold.show_date == payload.show_date,
            SeatHold.session == payload.session,
            SeatHold.user_id == user.id,
            SeatHold.seat.in_(payload.seats),
            SeatHold.expires_at > utcnow(),
        )
        .with_for_update()
    )
    if len(list(holds)) != len(payload.seats):
        raise HTTPException(409, "Hold expired")
    phone = "+" + "".join(char for char in payload.phone if char.isdigit())
    if not 8 <= len(phone) <= 16:
        raise HTTPException(422, "Invalid phone number")
    username = payload.telegram_username.strip().lstrip("@") or user.username

    # Freeze the unit price: a later admin price change must not rewrite history.
    price = await ticket_price(session, payload.movie_id, payload.show_date, payload.session)
    code = str(user.telegram_id)
    booking = Booking(
        user_id=user.id,
        movie_id=payload.movie_id,
        show_date=payload.show_date,
        session=payload.session,
        seats=",".join(payload.seats),
        code=code,
        ticket_price=price,
        total=len(payload.seats) * price,
        status="pending",
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        phone=phone,
        telegram_username=username,
        comment=payload.comment.strip(),
        promo_code=payload.promo_code.strip(),
    )
    # The viewer typed their details into the booking form; keep them on the
    # profile so the next booking is one tap. Existing values are never
    # overwritten — someone may be booking on a friend's behalf.
    if not user.first_name:
        user.first_name = booking.first_name
        user.name = booking.first_name or user.name
    if not user.last_name:
        user.last_name = booking.last_name
    if not user.phone:
        user.phone = phone

    session.add(booking)
    await session.flush()
    session.add(
        AdminNotification(
            booking_id=booking.id,
            message=f"Новая заявка: {booking.first_name} {booking.last_name}, {booking.phone}",
        )
    )
    await session.execute(
        SeatHold.__table__.delete().where(
            SeatHold.movie_id == payload.movie_id,
            SeatHold.show_date == payload.show_date,
            SeatHold.session == payload.session,
            SeatHold.user_id == user.id,
        )
    )
    # Composed while the booking is still loaded, so reading the text costs no
    # extra query after the commit expires the instance.
    movie = await session.get(Movie, payload.movie_id)
    admin_message = new_booking_admin_message(booking, movie.title if movie else "")
    await session.commit()
    # After the commit on purpose: the booking is already durable, so a dead
    # network or an admin who never started a chat with the bot cannot undo it.
    await notify_admins(admin_message)
    return {
        "status": "pending",
        "ticket_code": code,
        "ticket_price": price,
        "total": booking.total,
        "message": "Спасибо за бронирование! В ближайшее время администратор свяжется с вами.",
    }
