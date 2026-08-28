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
from sqlalchemy.orm.exc import StaleDataError

from backend.core.config import BLOCKING_STATUSES
from backend.core.db import utcnow
from backend.models import Booking, Movie, User
from backend.services.booking import ensure_bookable_slot, seats_taken_by_others
from backend.services.capacity import reassign_booking_tokens
from backend.services.settings import get_settings
from backend.services.slots import ensure_slot_is_bookable
from backend.services.telegram import generic_booking_confirmed_message, user_booking_notification

__all__ = [
    "BookingNotFound",
    "BookingTransitionConflict",
    "DecisionResult",
    "HallIsFull",
    "ProposalNotFound",
    "ProposedTimeRequired",
    "SeatsAlreadyTaken",
    "apply_decision",
    "apply_status",
    "answer_proposal",
]


class BookingNotFound(Exception):
    """No booking exists with the given id."""


class BookingTransitionConflict(Exception):
    """Another request changed this booking after it was read."""


async def _commit_transition(session: AsyncSession) -> None:
    try:
        await session.commit()
    except StaleDataError as error:
        await session.rollback()
        raise BookingTransitionConflict from error


class HallIsFull(Exception):
    """The hall cannot take this request's party any more."""


class SeatsAlreadyTaken(Exception):
    """A legacy movie-bound booking's own seats were taken by somebody else."""

    def __init__(self, seats: set[str]):
        self.seats = seats
        super().__init__(f"Seats already taken: {', '.join(sorted(seats))}")


class ProposedTimeRequired(Exception):
    """`propose` was called without a `proposed_session`."""


class ProposalNotFound(Exception):
    """The booking has no time proposed to answer, or it isn't the caller's own."""


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
    #: Set only by `answer_proposal` -- the live copy every admin gets, distinct
    #: from `viewer_message` which goes to the one person who just answered.
    admin_message: str = ""


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

    if action == "propose" and booking.status not in ("pending", "contacting"):
        raise BookingTransitionConflict("A terminal booking cannot receive a proposal")

    next_status = _ACTION_TO_STATUS.get(action)
    if next_status is not None:
        await _refuse_if_the_hall_cannot_take_it(session, booking, next_status)
    confirm_settings = (
        await get_settings(session) if action == "confirm" and movie is None else None
    )

    if action == "contact":
        booking.status = "contacting"
        booking.completed_at = None
        booking.viewer_hidden_at = None
        booking.admin_note = reason.strip()
        message = f"Мы получили заявку #{booking.id} и свяжемся с вами для подтверждения."
    elif action == "confirm":
        booking.status = "confirmed"
        booking.completed_at = None
        booking.viewer_hidden_at = None
        booking.proposed_session = ""
        booking.admin_note = ""
        if movie is None:
            message = generic_booking_confirmed_message(booking, confirm_settings)
        else:
            message = (
                f"Ваша бронь #{booking.id} подтверждена: {movie.title}, "
                f"{booking.show_date} {booking.session}."
            )
    elif action == "decline":
        booking.status = "cancelled"
        booking.completed_at = utcnow()
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
    await _commit_transition(session)

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
    user = await session.get(User, booking.user_id)
    movie = await session.get(Movie, booking.movie_id) if booking.movie_id is not None else None
    booking.status = status
    if status in ("cancelled", "watched") and booking.completed_at is None:
        booking.completed_at = utcnow()
    elif status not in ("cancelled", "watched"):
        booking.completed_at = None
        booking.viewer_hidden_at = None
    message = f"Заявка #{booking.id}: {status}"
    session.add(user_booking_notification(booking, "Статус бронирования изменён", message))
    await _commit_transition(session)

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


async def answer_proposal(
    session: AsyncSession, booking_id: int, telegram_id: int, action: str
) -> DecisionResult:
    """The viewer's own answer to a time the administrator proposed.

    `telegram_id` scopes the lookup to the caller's own booking -- the same
    ownership check `/api/profile/bookings/{id}/proposal` always enforced, and
    the one thing that stops a stranger who somehow learns a booking id from
    answering somebody else's proposal through the bot's buttons.

    Accepting is a fresh booking decision, not a flag flip: the slot must
    still be open and the hall must still have room there, exactly as moving
    a booking to any other time would require.
    """
    from backend.models import AdminNotification

    booking = await session.scalar(
        select(Booking).join(User, Booking.user_id == User.id).where(
            Booking.id == booking_id, User.telegram_id == telegram_id
        )
    )
    if (
        booking is None
        or not booking.proposed_session
        or booking.status not in ("pending", "contacting")
    ):
        raise ProposalNotFound(f"Booking #{booking_id} has no proposal for this caller")

    user = await session.get(User, booking.user_id)
    movie = await session.get(Movie, booking.movie_id) if booking.movie_id is not None else None

    if action == "accept":
        if booking.movie_id is None:
            await ensure_slot_is_bookable(session, booking.show_date, booking.proposed_session)
        else:
            await ensure_bookable_slot(session, booking.movie_id, booking.show_date, booking.proposed_session)
            clash = await seats_taken_by_others(session, booking, booking.proposed_session)
            if clash:
                raise SeatsAlreadyTaken(clash)
        moved = await reassign_booking_tokens(session, booking, booking.show_date, booking.proposed_session)
        if not moved:
            raise HallIsFull()
        booking.session = booking.proposed_session
        booking.proposed_session = ""
        booking.admin_note = ""
        admin_message = f"Клиент согласился на новое время заявки #{booking.id}: {booking.session}"
        viewer_message = f"Вы согласились на новое время заявки #{booking.id}: {booking.session}"
    else:
        booking.status = "cancelled"
        booking.completed_at = utcnow()
        booking.admin_note = "Клиент отказался от предложенного времени"
        admin_message = f"Клиент отказался от нового времени заявки #{booking.id}"
        viewer_message = f"Вы отказались от предложенного времени. Заявка #{booking.id} отменена."

    session.add(AdminNotification(booking_id=booking.id, message=admin_message))
    await _commit_transition(session)

    return DecisionResult(
        booking_id=booking.id,
        status=booking.status,
        proposed_session=booking.proposed_session,
        admin_note=booking.admin_note,
        viewer_telegram_id=user.telegram_id,
        viewer_message=viewer_message,
        telegram_username=booking.telegram_username or user.username,
        party_size=booking.party_size,
        total=booking.total,
        phone=booking.phone,
        show_date=booking.show_date,
        session_time=booking.session,
        movie_title=movie.title if movie is not None else None,
        admin_message=admin_message,
    )
