"""The generic booking contract: a date, a fixed time and a number of people.

Nothing in this router accepts or returns a `movie_id`, and nothing lets the
client name a price.  The viewer reserves places in the one auditorium; the
film and the payment are agreed with the administrator afterwards.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import current_user, get_db
from backend.core.config import DATE_PATTERN
from backend.core.security import optional_user
from backend.models import AdminNotification, Booking, CapacityHold, User
from backend.schemas.booking import BookingRequestIn, CapacityHoldIn
from backend.services.capacity import (
    allocate_capacity,
    date_usage,
    purge_expired_holds,
    release_capacity,
    slot_usage,
)
from backend.services.pricing import base_price
from backend.services.settings import get_settings
from backend.services.booking import session_has_started
from backend.services.slots import (
    active_slot_times,
    bookable_times,
    booking_window,
    ensure_slot_is_bookable,
)
from backend.services.telegram import (
    generic_booking_admin_message,
    generic_booking_user_message,
    notify_admins,
)

router = APIRouter(prefix="/api/booking", tags=["booking"])


async def _pricing(session: AsyncSession) -> dict[str, object]:
    """The one formula, spelled out for the client so it can render a total."""
    settings = await get_settings(session)
    return {
        "capacity": settings.hall_seats,
        "rows": settings.hall_rows,
        "cols": settings.hall_cols,
        "price": await base_price(session),
        "currency": settings.currency,
        "hold_minutes": settings.hold_minutes,
        "max_party_size": settings.hall_seats,
    }


@router.get("/dates")
async def booking_dates(
    user: User | None = Depends(optional_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Every date in the booking window, with how full it already is."""
    await purge_expired_holds(session)
    await session.commit()
    common = await _pricing(session)
    capacity = common["capacity"]
    # Read the schedule and the clock once: this is the landing screen, and a
    # query per day per slot would be a dozen round trips for one page.
    offset = (await get_settings(session)).timezone_offset_minutes
    times = await active_slot_times(session)
    dates: list[dict[str, object]] = []
    for show_date in await booking_window(session):
        usage = await date_usage(session, show_date, user_id=user.id if user else None)
        free = [
            usage[time].available if time in usage else capacity
            for time in times
            if not session_has_started(show_date, time, offset)
        ]
        dates.append(
            {
                "date": show_date,
                "slots": len([value for value in free if value > 0]),
                "available": max(free, default=0),
            }
        )
    return {**common, "dates": dates}


@router.get("/slots")
async def booking_slots(
    date: str = Query(pattern=DATE_PATTERN),
    user: User | None = Depends(optional_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """The fixed times still open on that date, with places left in each.

    A time that has already started is simply not offered, and neither is a
    date outside the booking window.
    """
    if date not in await booking_window(session):
        raise HTTPException(404, "Date is not open for booking")
    await purge_expired_holds(session)
    await session.commit()
    common = await _pricing(session)
    capacity = common["capacity"]
    usage = await date_usage(session, date, user_id=user.id if user else None)
    slots = []
    for start_time in await bookable_times(session, date):
        entry = usage.get(start_time)
        available = entry.available if entry else capacity
        slots.append(
            {
                "time": start_time,
                "capacity": capacity,
                "available": available,
                "taken": capacity - available,
                "mine": entry.mine if entry else 0,
                "price": common["price"],
            }
        )
    return {**common, "date": date, "slots": slots}


@router.post("/holds")
async def hold_capacity(
    payload: CapacityHoldIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Reserve `party_size` places for a few minutes while the form is filled in.

    The viewer picks a number, never a chair: the backend allocates the internal
    capacity tokens itself and the response never names one.
    """
    await ensure_slot_is_bookable(session, payload.date, payload.time)
    settings = await get_settings(session)
    # Read every ORM value as a plain number up front. Losing the race for a
    # token rolls the session back, and a rollback expires loaded instances
    # whatever `expire_on_commit` says -- touching `user.id` afterwards would
    # then try to reload it from a synchronous attribute access and blow up.
    capacity, hold_minutes = settings.hall_seats, settings.hold_minutes
    user_id = user.id
    if payload.party_size > capacity:
        raise HTTPException(422, f"The hall seats {capacity} people")

    tokens = await allocate_capacity(session, payload.date, payload.time, user_id, payload.party_size)
    if tokens is None:
        usage = await slot_usage(session, payload.date, payload.time, user_id=user_id)
        raise HTTPException(409, f"Only {usage.available} places left for this time")

    price = await base_price(session)
    usage = await slot_usage(session, payload.date, payload.time, user_id=user_id)
    return {
        "date": payload.date,
        "time": payload.time,
        "party_size": payload.party_size,
        "expires_in_minutes": hold_minutes,
        "ticket_price": price,
        "total": payload.party_size * price,
        "capacity": capacity,
        "available": usage.available,
    }


@router.delete("/holds")
async def release_hold(
    date: str = Query(pattern=DATE_PATTERN),
    time: str = Query(default=""),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Give the places back when the viewer changes their mind or walks away."""
    await release_capacity(session, date, time, user.id)
    await session.commit()
    return {"status": "released"}


@router.post("/requests")
async def create_request(
    payload: BookingRequestIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """File the request the administrator will phone back about.

    Payment happens outside the app: the request is `pending`, the administrator
    contacts the viewer, takes the transfer by hand and only then confirms.
    There is no gateway and no `paid` status anywhere in this flow.
    """
    await ensure_slot_is_bookable(session, payload.date, payload.time)
    await purge_expired_holds(session)
    tokens = sorted(
        hold.token
        for hold in await session.scalars(
            select(CapacityHold).where(
                CapacityHold.show_date == payload.date,
                CapacityHold.start_time == payload.time,
                CapacityHold.user_id == user.id,
            )
        )
    )
    if len(tokens) != payload.party_size:
        # The hold is the allocation. Without a live one for exactly this party
        # the places were never reserved, or they have since expired.
        raise HTTPException(409, "Hold expired")

    phone = "+" + "".join(char for char in payload.phone if char.isdigit())
    if not 8 <= len(phone) <= 16:
        raise HTTPException(422, "Invalid phone number")
    username = payload.telegram_username.strip().lstrip("@") or user.username

    # Freeze the unit price: a later admin price change must not rewrite history.
    price = await base_price(session)
    booking = Booking(
        user_id=user.id,
        movie_id=None,
        show_date=payload.date,
        session=payload.time,
        seats=",".join(str(token) for token in tokens),
        party_size=payload.party_size,
        code=str(user.telegram_id),
        ticket_price=price,
        total=payload.party_size * price,
        status="pending",
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        phone=phone,
        telegram_username=username,
        comment=payload.comment.strip(),
        promo_code=payload.promo_code.strip(),
    )
    # Keep the contact details on the profile so the next request is one tap.
    # Existing values are never overwritten: somebody may be booking for a friend.
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
    await release_capacity(session, payload.date, payload.time, user.id)
    # Composed while the booking is still loaded, so reading the text costs no
    # extra query after the commit expires the instance.
    settings = await get_settings(session)
    admin_message = generic_booking_admin_message(booking)
    user_message = generic_booking_user_message(booking, settings)
    booking_id = booking.id
    ticket_code = booking.code
    await session.commit()
    # After the commit on purpose: the request is already durable, so a dead
    # network or an admin who never started a chat cannot undo it.
    await notify_admins(admin_message)
    return {
        "id": booking_id,
        "status": "pending",
        "ticket_code": ticket_code,
        "date": payload.date,
        "time": payload.time,
        "party_size": payload.party_size,
        "ticket_price": price,
        "total": payload.party_size * price,
        "message": user_message,
    }
