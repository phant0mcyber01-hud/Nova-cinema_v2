"""The one place a booking's status changes -- from the panel or from the bot.

`update_booking_status` and `decide_booking` in the admin router used to hold
this logic inline. Pulling it out means the Telegram inline-button flow calls
exactly the same rules instead of a second copy that could quietly drift:
the hall-capacity check, the frozen price, which message the viewer receives,
and which fields go on the record are decided in one function either way.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import BLOCKING_STATUSES
from backend.core.db import utcnow
from backend.models import Booking, Movie, User
from backend.services.booking import seats_taken_by_others
from backend.services.capacity import reassign_booking_tokens
from backend.services.settings import get_settings
from backend.services.telegram import generic_booking_confirmed_message, user_booking_notification

__all__ = [
    "BookingNotFound",
    "DecisionResult",
    "HallIsFull",
    "ProposedTimeRequired",
    "SeatsAlreadyTaken",
    "apply_decision",
]


class BookingNotFound(Exception):
    """No booking exists with the given id."""


class HallIsFull(Exception):
    """The hall cannot take this request's party any more."""


class SeatsAlreadyTaken(Exception):
    """A legacy movie-bound booking's own seats were taken by somebody else."""

    def __init__(self, seats: set[str]):
        self.seats = seats
        super().__init__(f"Seats already taken: {', '.join(sorted(seats))}")


class ProposedTimeRequired(Exception):
    """`propose` was called without a `proposed_session`."""


@dataclass
class DecisionResult:
    """Everything a caller -- the HTTP router or the bot callback -- needs to render."""

    booking_id: int
    status: str
    proposed_session: str
    admin_note: str
    viewer_telegram_id: int
    viewer_message: str
    telegram_username: str
    party_size: int
    total: int
    phone: str
    show_date: str
    session_time: str
    movie_title: str | None


_ACTION_TO_STATUS = {"contact": "contacting", "confirm": "confirmed", "decline": "cancelled"}


async def _refuse_if_the_hall_cannot_take_it(
    session: AsyncSession, booking: Booking, next_status: str
) -> None:
    """Block a status change that would put a request back into a full hall.

    Reviving a cancelled request is not a flag flip: the places it used to
    hold were released the moment it was cancelled, and somebody else may be
    sitting in them. A generic booking is re-allocated fresh capacity tokens,
    because the numbers it carried mean nothing once they were given away.
    """
    if next_status not in BLOCKING_STATUSES or booking.status in BLOCKING_STATUSES:
        return
    if booking.movie_id is not None:
        clash = await seats_taken_by_others(session, booking)
        if clash:
            raise SeatsAlreadyTaken(clash)
    if not await reassign_booking_tokens(session, booking, booking.show_date, booking.session):
        raise HallIsFull()


async def apply_decision(
    session: AsyncSession,
    booking_id: int,
    action: str,
    *,
    reason: str = "",
    proposed_session: str = "",
) -> DecisionResult:
    """Run one admin decision (`contact`/`confirm`/`decline`/`propose`) to completion.

    Commits before returning. The caller is responsible for actually sending
    `viewer_message` to `viewer_telegram_id` -- this function only decides
    what happened and what the viewer should be told.
    """
    row = await session.execute(
        select(Booking, User, Movie)
        .join(User, Booking.user_id == User.id)
        .outerjoin(Movie, Booking.movie_id == Movie.id)
        .where(Booking.id == booking_id)
    )
    item = row.first()
    if item is None:
        raise BookingNotFound(f"Booking #{booking_id} not found")
    booking, user, movie = item

    next_status = _ACTION_TO_STATUS.get(action)
    if next_status is not None:
        await _refuse_if_the_hall_cannot_take_it(session, booking, next_status)

    if action == "contact":
        booking.status = "contacting"
        booking.admin_note = reason.strip()
        message = f"Мы получили заявку #{booking.id} и свяжемся с вами для подтверждения."
    elif action == "confirm":
        booking.status = "confirmed"
        booking.proposed_session = ""
        booking.admin_note = ""
        if movie is None:
            message = generic_booking_confirmed_message(booking, await get_settings(session))
        else:
            message = (
                f"Ваша бронь #{booking.id} подтверждена: {movie.title}, "
                f"{booking.show_date} {booking.session}."
            )
    elif action == "decline":
        booking.status = "cancelled"
        booking.admin_note = reason.strip()
        message = f"Заявка #{booking.id} отклонена. Причина: {booking.admin_note or 'не указана'}."
    elif action == "propose":
        if not proposed_session:
            raise ProposedTimeRequired("A proposed time is required")
        booking.proposed_session = proposed_session
        booking.admin_note = reason.strip()
        message = (
            f"Nova Cinema предлагает другое время для заявки #{booking.id}: "
            f"{booking.proposed_session}. {booking.admin_note}"
        ).strip()
    else:
        raise ValueError(f"Unknown action {action!r}")

    session.add(user_booking_notification(booking, "Nova Cinema", message))
    await session.commit()

    return DecisionResult(
        booking_id=booking.id,
        status=booking.status,
        proposed_session=booking.proposed_session,
        admin_note=booking.admin_note,
        viewer_telegram_id=user.telegram_id,
        viewer_message=message,
        telegram_username=booking.telegram_username or user.username,
        party_size=booking.party_size,
        total=booking.total,
        phone=booking.phone,
        show_date=booking.show_date,
        session_time=booking.session,
        movie_title=movie.title if movie is not None else None,
    )


async def apply_status(session: AsyncSession, booking_id: int, status: str) -> DecisionResult:
    """The blunt panel action: set a status directly (used for `watched`/manual overrides)."""
    booking = await session.get(Booking, booking_id)
    if booking is None:
        raise BookingNotFound(f"Booking #{booking_id} not found")
    await _refuse_if_the_hall_cannot_take_it(session, booking, status)
    booking.status = status
    if status == "watched" and booking.completed_at is None:
        booking.completed_at = utcnow()

    user = await session.get(User, booking.user_id)
    movie = await session.get(Movie, booking.movie_id) if booking.movie_id is not None else None
    message = f"Заявка #{booking.id}: {status}"
    session.add(user_booking_notification(booking, "Статус бронирования изменён", message))
    await session.commit()

    return DecisionResult(
        booking_id=booking.id,
        status=booking.status,
        proposed_session=booking.proposed_session,
        admin_note=booking.admin_note,
        viewer_telegram_id=user.telegram_id if user else 0,
        viewer_message=message,
        telegram_username=booking.telegram_username or (user.username if user else ""),
        party_size=booking.party_size,
        total=booking.total,
        phone=booking.phone,
        show_date=booking.show_date,
        session_time=booking.session,
        movie_title=movie.title if movie is not None else None,
    )
