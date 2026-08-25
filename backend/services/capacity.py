"""How full the hall is at a date and a time -- and nothing else.

Nova Cinema has one auditorium, so the booking inventory is a date plus a fixed
time.  Every count in this module is scoped by exactly those two columns and
never by `movie_id`: two viewers who agreed different films with the
administrator for 18:00 are still sitting in the same twelve chairs.

Places are handed out as *virtual capacity tokens*, `1..hall_seats`.  A token is
not a seat.  The viewer never picks one, never sees one and is promised no row
or chair -- the token exists so the unique key on `capacity_holds` is what
refuses to sell the thirteenth place, rather than a check in Python that two
parallel requests can both walk past.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import BLOCKING_STATUSES
from backend.core.db import utcnow
from backend.models import Booking, CapacityHold, SeatHold
from backend.services.settings import get_settings

__all__ = [
    "SlotUsage",
    "allocate_capacity",
    "booking_party_size",
    "purge_expired_holds",
    "reassign_booking_tokens",
    "release_capacity",
    "slot_usage",
]

#: How many times a hold retries after losing the unique key. Two requests that
#: both pick the lowest free tokens collide even when the hall is nearly empty;
#: recomputing once or twice turns that into a success instead of a false 409.
ALLOCATION_ATTEMPTS = 3


def booking_party_size(booking: Booking) -> int:
    """Places a booking occupies, for rows written before `party_size` existed."""
    if booking.party_size:
        return booking.party_size
    return len([seat for seat in booking.seats.split(",") if seat])


def booking_tokens(booking: Booking) -> set[int]:
    """The capacity tokens a generic booking owns.

    A legacy movie-bound booking stores real seat labels ("2-3") instead, and
    owns no token: it still consumes places, but which ones is meaningless.
    """
    if booking.movie_id is not None:
        return set()
    tokens = set()
    for part in booking.seats.split(","):
        part = part.strip()
        if part.isdigit():
            tokens.add(int(part))
    return tokens


@dataclass
class SlotUsage:
    """What one date+time looks like right now."""

    capacity: int
    #: Tokens somebody else is holding, or a generic booking already owns.
    taken_tokens: set[int] = field(default_factory=set)
    #: Places held by movie-bound legacy bookings, which own no token.
    legacy_places: int = 0
    #: Capacity tokens this caller is holding at the moment.
    mine: int = 0

    @property
    def available(self) -> int:
        """Places this caller may still take -- their own hold is not in the way."""
        return max(self.capacity - len(self.taken_tokens) - self.legacy_places, 0)

    @property
    def taken(self) -> int:
        return self.capacity - self.available

    def free_tokens(self) -> list[int]:
        """Tokens that can be handed out, lowest first.

        The legacy places are subtracted off the front: those bookings occupy
        the hall without owning a token, so the pool has to shrink by their
        size before anything is allocated.
        """
        free = [token for token in range(1, self.capacity + 1) if token not in self.taken_tokens]
        return free[self.legacy_places :] if self.legacy_places else free


async def purge_expired_holds(session: AsyncSession) -> None:
    await session.execute(CapacityHold.__table__.delete().where(CapacityHold.expires_at < utcnow()))


async def date_usage(
    session: AsyncSession,
    show_date: str,
    *,
    user_id: int | None = None,
    exclude_booking_id: int | None = None,
) -> dict[str, SlotUsage]:
    """One pass over a whole date, so a five-slot page is not five round trips."""
    settings = await get_settings(session)
    capacity = settings.hall_seats
    usage: dict[str, SlotUsage] = {}

    def slot(start_time: str) -> SlotUsage:
        return usage.setdefault(start_time, SlotUsage(capacity=capacity))

    query = select(Booking).where(
        Booking.show_date == show_date, Booking.status.in_(BLOCKING_STATUSES)
    )
    if exclude_booking_id is not None:
        query = query.where(Booking.id != exclude_booking_id)
    for booking in await session.scalars(query):
        entry = slot(booking.session)
        tokens = booking_tokens(booking)
        if tokens:
            entry.taken_tokens |= tokens
        else:
            entry.legacy_places += booking_party_size(booking)

    now = utcnow()
    holds = await session.scalars(
        select(CapacityHold).where(
            CapacityHold.show_date == show_date, CapacityHold.expires_at > now
        )
    )
    for hold in holds:
        entry = slot(hold.start_time)
        if user_id is not None and hold.user_id == user_id:
            entry.mine += 1
        else:
            entry.taken_tokens.add(hold.token)

    # The legacy movie-bound flow holds real seats in its own table. They own no
    # capacity token, but they are people sitting in the same twelve chairs.
    legacy_holds = await session.scalars(
        select(SeatHold).where(SeatHold.show_date == show_date, SeatHold.expires_at > now)
    )
    for hold in legacy_holds:
        entry = slot(hold.session)
        if user_id is not None and hold.user_id == user_id:
            entry.mine += 1
        else:
            entry.legacy_places += 1
    return usage


async def slot_usage(
    session: AsyncSession,
    show_date: str,
    start_time: str,
    *,
    user_id: int | None = None,
    exclude_booking_id: int | None = None,
) -> SlotUsage:
    usage = await date_usage(
        session, show_date, user_id=user_id, exclude_booking_id=exclude_booking_id
    )
    if start_time in usage:
        return usage[start_time]
    return SlotUsage(capacity=(await get_settings(session)).hall_seats)


async def release_capacity(
    session: AsyncSession, show_date: str, start_time: str, user_id: int
) -> None:
    await session.execute(
        CapacityHold.__table__.delete().where(
            CapacityHold.show_date == show_date,
            CapacityHold.start_time == start_time,
            CapacityHold.user_id == user_id,
        )
    )


async def allocate_capacity(
    session: AsyncSession, show_date: str, start_time: str, user_id: int, party_size: int
) -> list[int] | None:
    """Claim `party_size` tokens for this slot, replacing the caller's own hold.

    Returns the allocated tokens, or None when the hall cannot take the party.
    The database is the arbiter: the caller's chosen tokens are inserted under
    `uq_capacity_hold`, and a parallel request that picked the same numbers
    loses there rather than in a check both of them passed.
    """
    hold_minutes = (await get_settings(session)).hold_minutes
    for _ in range(ALLOCATION_ATTEMPTS):
        await purge_expired_holds(session)
        await session.commit()
        # `user_id` keeps the caller's own hold out of the way: they are about to
        # replace it, so their current places are theirs to take again.
        usage = await slot_usage(session, show_date, start_time, user_id=user_id)
        free = usage.free_tokens()
        if len(free) < party_size:
            # Nothing has been written yet, so there is nothing to undo -- and
            # no rolled-back session for the caller to trip over.
            return None
        chosen = free[:party_size]
        expires = utcnow() + timedelta(minutes=hold_minutes)
        await release_capacity(session, show_date, start_time, user_id)
        session.add_all(
            CapacityHold(
                show_date=show_date,
                start_time=start_time,
                token=token,
                user_id=user_id,
                expires_at=expires,
            )
            for token in chosen
        )
        try:
            await session.commit()
        except IntegrityError:
            # uq_capacity_hold fired: somebody claimed one of these tokens
            # between the read above and this insert. Recompute and try again;
            # only a genuinely full hall ends the loop.
            await session.rollback()
            continue
        return chosen
    return None


async def reassign_booking_tokens(
    session: AsyncSession, booking: Booking, show_date: str, start_time: str
) -> bool:
    """Re-allocate a generic booking's places at a slot, or report that it cannot fit.

    Needed wherever a booking re-enters the hall: reviving a cancelled request,
    and moving one to the time the administrator proposed.  Its old tokens mean
    nothing there -- somebody else may hold exactly those numbers -- so the
    booking is given a fresh set, and a hall that cannot take the party says so
    instead of quietly seating thirteen people.
    """
    if booking.movie_id is not None:
        # A legacy movie-bound row stores seat labels and owns no token; only
        # the head-count check below applies to it.
        usage = await slot_usage(session, show_date, start_time, exclude_booking_id=booking.id)
        return usage.available >= booking_party_size(booking)
    usage = await slot_usage(session, show_date, start_time, exclude_booking_id=booking.id)
    free = usage.free_tokens()
    party_size = booking_party_size(booking)
    if len(free) < party_size:
        return False
    booking.seats = ",".join(str(token) for token in free[:party_size])
    return True
