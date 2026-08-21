from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import current_user, get_db
from backend.core.config import BLOCKING_STATUSES
from backend.core.db import utcnow
from backend.models import AdminNotification, Booking, SeatHold, User
from backend.schemas.booking import BookingConfirmIn, HoldIn
from backend.services.booking import ensure_show
from backend.services.hall import valid_seat
from backend.services.pricing import ticket_price
from backend.services.settings import get_settings

router = APIRouter(tags=["booking"])


async def _taken_seats(session: AsyncSession, movie_id: int, show_date: str, session_time: str) -> set[str]:
    bookings = await session.scalars(
        select(Booking).where(
            Booking.movie_id == movie_id,
            Booking.show_date == show_date,
            Booking.session == session_time,
            Booking.status.in_(BLOCKING_STATUSES),
        )
    )
    return {seat for booking in bookings for seat in booking.seats.split(",") if seat}


@router.get("/api/sessions/{movie_id}/seats")
async def session_seats(
    movie_id: int,
    show_date: str,
    session_time: str,
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    await ensure_show(session, movie_id, show_date, session_time)
    settings = await get_settings(session)
    await session.execute(SeatHold.__table__.delete().where(SeatHold.expires_at < utcnow()))
    await session.commit()
    holds = await session.scalars(
        select(SeatHold).where(
            SeatHold.movie_id == movie_id,
            SeatHold.show_date == show_date,
            SeatHold.session == session_time,
        )
    )
    taken = await _taken_seats(session, movie_id, show_date, session_time)
    taken |= {hold.seat for hold in holds}
    return {
        "rows": settings.hall_rows,
        "cols": settings.hall_cols,
        "seats_count": settings.hall_seats,
        "max_seats": settings.max_seats_per_booking,
        "price": await ticket_price(session, movie_id, show_date, session_time),
        "currency": settings.currency,
        "taken": sorted(taken),
    }


@router.post("/api/holds")
async def hold_seats(
    payload: HoldIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    await ensure_show(session, payload.movie_id, payload.show_date, payload.session)
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
    await session.commit()
    price = await ticket_price(session, payload.movie_id, payload.show_date, payload.session)
    return {
        "expires_at": expires,
        "seats": payload.seats,
        "ticket_price": price,
        "total": len(payload.seats) * price,
    }


@router.post("/api/bookings/confirm")
async def confirm_booking(
    payload: BookingConfirmIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    await ensure_show(session, payload.movie_id, payload.show_date, payload.session)
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
    )
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
    await session.commit()
    return {
        "status": "pending",
        "ticket_code": code,
        "ticket_price": price,
        "total": booking.total,
        "message": "Спасибо за бронирование! В ближайшее время администратор свяжется с вами.",
    }
