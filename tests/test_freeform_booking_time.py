"""Freeform booking time: the viewer names the hour, the seat lock is unchanged.

What was relaxed is *which* time may be requested -- the admin's configured
slots are suggestions now, not the whitelist. What must not move is the
guarantee the client asked to keep: one seat at one time belongs to exactly one
viewer. The lock itself is `uq_seat_hold` on
(movie_id, show_date, session, seat), and `session` holds the freeform string
verbatim, so a different hour is simply a different key.
"""
from __future__ import annotations

import asyncio
from datetime import date, timedelta

from sqlalchemy import select

from backend.core.db import SessionLocal
from backend.models import Booking, Show
from tests.conftest import (
    OTHER_ID,
    SESSION,
    SHOW_DATE,
    TODAY,
    USER_ID,
    auth_header,
    login,
)

CONTACT = {
    "first_name": "Иван",
    "last_name": "Петров",
    "phone": "+998 91 326 20 65",
    "telegram_username": "ivanp",
    "comment": "",
}

#: Deliberately not the 19:00 the `movie` fixture puts in `shows`.
FREEFORM = "07:35"
OTHER_FREEFORM = "22:47"


async def _seats(client, movie_id: int, session_time: str = FREEFORM, show_date: str = SHOW_DATE):
    return await client.get(
        f"/api/sessions/{movie_id}/seats",
        params={"show_date": show_date, "session_time": session_time},
    )


async def _hold(client, movie_id: int, seats: list[str], token: str, session_time: str = FREEFORM):
    return await client.post(
        "/api/holds",
        json={"movie_id": movie_id, "show_date": SHOW_DATE, "session": session_time, "seats": seats},
        headers=auth_header(token),
    )


async def _book(client, movie_id: int, seats: list[str], token: str, session_time: str = FREEFORM):
    payload = {"movie_id": movie_id, "show_date": SHOW_DATE, "session": session_time, "seats": seats}
    hold = await _hold(client, movie_id, seats, token, session_time)
    assert hold.status_code == 200, hold.text
    return await client.post(
        "/api/bookings/confirm", json={**payload, **CONTACT}, headers=auth_header(token)
    )


# --- what was relaxed --------------------------------------------------------


async def test_a_time_the_admin_never_configured_is_bookable(client, movie):
    """The old rule answered 404 for any HH:MM that was not a row in `shows`."""
    listed = (await client.get(f"/api/movies/{movie.id}/sessions?show_date={SHOW_DATE}")).json()
    assert listed["sessions"] == [SESSION], "the fixture configures one slot only"
    assert FREEFORM not in listed["sessions"], "the time under test must be unscheduled"

    seats = await _seats(client, movie.id)
    assert seats.status_code == 200, seats.text

    user = await login(client, USER_ID)
    booked = await _book(client, movie.id, ["1-1"], user)
    assert booked.status_code == 200, booked.text

    async with SessionLocal() as session:
        row = await session.scalar(select(Booking))
    assert row.session == FREEFORM, "the hour the viewer asked for is what gets stored"


async def test_a_freeform_time_is_priced_from_the_movie_not_a_missing_slot(client, movie):
    """No `shows` row means no per-slot override, so the base price applies."""
    async with SessionLocal() as session:
        session.add(
            Show(movie_id=movie.id, show_date=SHOW_DATE, start_time="21:30", ticket_price=51000)
        )
        await session.commit()

    assert (await _seats(client, movie.id, "21:30")).json()["price"] == 51000, (
        "an admin slot keeps its own price override"
    )
    assert (await _seats(client, movie.id)).json()["price"] == 30000, (
        "a freeform hour falls back instead of failing"
    )


async def test_a_day_the_movie_does_not_play_is_still_refused(client, movie):
    """The date gate is the part of the schedule that was kept."""
    quiet_day = (date.fromisoformat(SHOW_DATE) + timedelta(days=1)).isoformat()

    assert (await _seats(client, movie.id, FREEFORM, quiet_day)).status_code == 404

    user = await login(client, USER_ID)
    hold = await client.post(
        "/api/holds",
        json={"movie_id": movie.id, "show_date": quiet_day, "session": FREEFORM, "seats": ["1-1"]},
        headers=auth_header(user),
    )
    assert hold.status_code == 404, "a freeform time must not conjure up a screening"


async def test_a_malformed_time_is_still_refused(client, movie):
    for bad in ("24:30", "7:5", "19:60", "hall", ""):
        assert (await _seats(client, movie.id, bad)).status_code == 404, f"{bad!r} was accepted"

    user = await login(client, USER_ID)
    hold = await _hold(client, movie.id, ["1-1"], user, "24:30")
    assert hold.status_code == 422, "the payload schema rejects it before the service does"


async def test_a_freeform_time_that_has_already_passed_is_refused(client, movie, cinema_clock):
    """It is noon at the cinema; 09:15 today is gone, scheduled or not."""
    async with SessionLocal() as session:
        session.add(Show(movie_id=movie.id, show_date=TODAY, start_time="21:00"))
        await session.commit()

    assert (await _seats(client, movie.id, "09:15", TODAY)).status_code == 404

    user = await login(client, USER_ID)
    hold = await client.post(
        "/api/holds",
        json={"movie_id": movie.id, "show_date": TODAY, "session": "09:15", "seats": ["1-1"]},
        headers=auth_header(user),
    )
    assert hold.status_code == 404

    later = await client.post(
        "/api/holds",
        json={"movie_id": movie.id, "show_date": TODAY, "session": "20:05", "seats": ["1-1"]},
        headers=auth_header(user),
    )
    assert later.status_code == 200, "a freeform hour still ahead of the clock is fine"


# --- what was strictly preserved: one seat, one time, one viewer -------------


async def test_two_viewers_cannot_take_one_seat_at_the_same_freeform_time(client, movie):
    first = await login(client, USER_ID)
    second = await login(client, OTHER_ID, "other")

    assert (await _hold(client, movie.id, ["1-1"], first)).status_code == 200

    held = await _hold(client, movie.id, ["1-1"], second)
    assert held.status_code == 409, "the seat is being taken right now"
    assert "held" in held.json()["detail"].lower()

    assert (await _book(client, movie.id, ["1-1"], first)).status_code == 200

    booked = await _hold(client, movie.id, ["1-1"], second)
    assert booked.status_code == 409, "and it stays taken once the request exists"
    assert "booked" in booked.json()["detail"].lower()

    async with SessionLocal() as session:
        rows = list(await session.scalars(select(Booking)))
    assert len(rows) == 1, "exactly one viewer may hold that seat at that hour"


async def test_simultaneous_freeform_requests_yield_one_winner(client, movie):
    """`uq_seat_hold` still arbitrates when the time never came from `shows`."""
    first = await login(client, USER_ID)
    second = await login(client, OTHER_ID, "other")

    results = await asyncio.gather(
        _hold(client, movie.id, ["2-1"], first),
        _hold(client, movie.id, ["2-1"], second),
        return_exceptions=True,
    )
    codes = sorted(item.status_code for item in results if not isinstance(item, BaseException))
    assert 500 not in codes, f"a race must not surface as a server error: {codes}"
    assert codes.count(200) == 1, f"exactly one holder expected, got {codes}"
    assert codes.count(409) == 1, f"the loser must be told the seat is taken, got {codes}"


async def test_the_same_seat_at_two_different_freeform_times_is_two_bookings(client, movie):
    """Different hours are different keys; neither viewer blocks the other."""
    first = await login(client, USER_ID)
    second = await login(client, OTHER_ID, "other")

    early = await _book(client, movie.id, ["1-1"], first, FREEFORM)
    assert early.status_code == 200, early.text
    late = await _book(client, movie.id, ["1-1"], second, OTHER_FREEFORM)
    assert late.status_code == 200, late.text

    async with SessionLocal() as session:
        rows = list(await session.scalars(select(Booking).order_by(Booking.session)))
    assert [row.session for row in rows] == [FREEFORM, OTHER_FREEFORM]
    assert [row.seats for row in rows] == ["1-1", "1-1"]

    assert (await _seats(client, movie.id, FREEFORM)).json()["taken"] == ["1-1"]
    assert (await _seats(client, movie.id, OTHER_FREEFORM)).json()["taken"] == ["1-1"]
    assert (await _seats(client, movie.id, "13:20")).json()["taken"] == [], (
        "an hour nobody asked for is untouched"
    )
