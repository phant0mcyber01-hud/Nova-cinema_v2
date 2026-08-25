"""Stage 10: four seat states and protection against double booking.

The spec is explicit that the backend re-checks seats and that the frontend is
not to be trusted, so every assertion here goes through the API.
"""
from __future__ import annotations

import asyncio
from datetime import timedelta

from sqlalchemy import select

from backend.core.db import SessionLocal, utcnow
from backend.models import Booking, CinemaSettings, SeatHold
from tests.conftest import ADMIN_ID, OTHER_ID, SESSION, SHOW_DATE, USER_ID, auth_header, login

CONTACT = {
    "first_name": "Иван",
    "last_name": "Петров",
    "phone": "+998 91 326 20 65",
    "telegram_username": "ivanp",
    "comment": "",
}


async def _seats(client, movie_id: int, token: str | None = None):
    headers = auth_header(token) if token else {}
    response = await client.get(
        f"/api/sessions/{movie_id}/seats",
        params={"show_date": SHOW_DATE, "session_time": SESSION},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _hold(client, movie_id: int, seats: list[str], token: str):
    return await client.post(
        "/api/holds",
        json={"movie_id": movie_id, "show_date": SHOW_DATE, "session": SESSION, "seats": seats},
        headers=auth_header(token),
    )


async def _book(client, movie_id: int, seats: list[str], token: str):
    payload = {"movie_id": movie_id, "show_date": SHOW_DATE, "session": SESSION, "seats": seats}
    await _hold(client, movie_id, seats, token)
    return await client.post("/api/bookings/confirm", json={**payload, **CONTACT}, headers=auth_header(token))


# --- four seat states --------------------------------------------------------


async def test_empty_hall_reports_every_seat_free(client, movie):
    hall = await _seats(client, movie.id)
    assert hall["booked"] == []
    assert hall["awaiting"] == []
    assert hall["mine"] == []
    assert hall["taken"] == []


async def test_a_request_awaiting_the_admin_is_not_reported_as_booked(client, movie):
    user = await login(client, USER_ID)
    assert (await _book(client, movie.id, ["1-1"], user)).status_code == 200

    hall = await _seats(client, movie.id)
    assert hall["awaiting"] == ["1-1"], "a pending request must read as awaiting confirmation"
    assert hall["booked"] == []
    assert hall["taken"] == ["1-1"]


async def test_confirmed_request_moves_the_seat_to_booked(client, movie):
    user = await login(client, USER_ID)
    await _book(client, movie.id, ["1-1"], user)
    admin = await login(client, ADMIN_ID, "admin")
    booking_id = (await client.get("/api/admin/bookings", headers=auth_header(admin))).json()[0]["id"]
    await client.patch(
        f"/api/admin/bookings/{booking_id}/decision",
        json={"action": "confirm", "reason": "", "proposed_session": ""},
        headers=auth_header(admin),
    )

    hall = await _seats(client, movie.id)
    assert hall["booked"] == ["1-1"]
    assert hall["awaiting"] == []


async def test_contacting_still_counts_as_awaiting(client, movie):
    user = await login(client, USER_ID)
    await _book(client, movie.id, ["2-2"], user)
    admin = await login(client, ADMIN_ID, "admin")
    booking_id = (await client.get("/api/admin/bookings", headers=auth_header(admin))).json()[0]["id"]
    await client.patch(
        f"/api/admin/bookings/{booking_id}/decision",
        json={"action": "contact", "reason": "", "proposed_session": ""},
        headers=auth_header(admin),
    )

    hall = await _seats(client, movie.id)
    assert hall["awaiting"] == ["2-2"]
    assert hall["booked"] == []


async def test_cancelled_request_frees_the_seat_completely(client, movie):
    user = await login(client, USER_ID)
    await _book(client, movie.id, ["3-3"], user)
    admin = await login(client, ADMIN_ID, "admin")
    booking_id = (await client.get("/api/admin/bookings", headers=auth_header(admin))).json()[0]["id"]
    await client.patch(
        f"/api/admin/bookings/{booking_id}/decision",
        json={"action": "decline", "reason": "нет мест", "proposed_session": ""},
        headers=auth_header(admin),
    )

    hall = await _seats(client, movie.id)
    assert hall["taken"] == []
    assert hall["awaiting"] == []
    assert hall["booked"] == []


# --- own hold vs somebody else's --------------------------------------------


async def test_my_own_hold_is_mine_not_a_blocked_seat(client, movie):
    user = await login(client, USER_ID)
    assert (await _hold(client, movie.id, ["1-4"], user)).status_code == 200

    mine = await _seats(client, movie.id, user)
    assert mine["mine"] == ["1-4"]
    assert mine["awaiting"] == [], "my own hold must not read as blocked to me"

    stranger = await login(client, OTHER_ID, "other")
    theirs = await _seats(client, movie.id, stranger)
    assert theirs["mine"] == []
    assert theirs["awaiting"] == ["1-4"], "somebody else is taking that seat right now"


async def test_anonymous_viewer_sees_a_hold_as_awaiting(client, movie):
    user = await login(client, USER_ID)
    await _hold(client, movie.id, ["2-4"], user)
    hall = await _seats(client, movie.id)
    assert hall["awaiting"] == ["2-4"]
    assert hall["mine"] == []


async def test_expired_hold_releases_the_seat(client, movie):
    user = await login(client, USER_ID)
    await _hold(client, movie.id, ["1-4"], user)
    async with SessionLocal() as session:
        hold = await session.scalar(select(SeatHold))
        hold.expires_at = utcnow() - timedelta(minutes=1)
        await session.commit()

    hall = await _seats(client, movie.id)
    assert hall["taken"] == [], "an expired hold must not keep the seat"


# --- double booking ----------------------------------------------------------


async def test_second_viewer_cannot_hold_a_held_seat(client, movie):
    first = await login(client, USER_ID)
    second = await login(client, OTHER_ID, "other")
    assert (await _hold(client, movie.id, ["1-1"], first)).status_code == 200

    clash = await _hold(client, movie.id, ["1-1"], second)
    assert clash.status_code == 409
    assert "held" in clash.json()["detail"].lower()


async def test_second_viewer_cannot_hold_a_booked_seat(client, movie):
    first = await login(client, USER_ID)
    await _book(client, movie.id, ["1-2"], first)

    second = await login(client, OTHER_ID, "other")
    clash = await _hold(client, movie.id, ["1-2"], second)
    assert clash.status_code == 409
    assert "booked" in clash.json()["detail"].lower()


async def test_simultaneous_holds_yield_one_winner_and_an_honest_conflict(client, movie):
    """The unique index arbitrates; the loser must get 409, never a 500."""
    first = await login(client, USER_ID)
    second = await login(client, OTHER_ID, "other")

    results = await asyncio.gather(
        _hold(client, movie.id, ["2-1"], first),
        _hold(client, movie.id, ["2-1"], second),
        return_exceptions=True,
    )
    codes = sorted(
        item.status_code for item in results if not isinstance(item, BaseException)
    )
    assert 500 not in codes, f"a race must not surface as a server error: {codes}"
    assert codes.count(200) == 1, f"exactly one holder expected, got {codes}"
    assert codes.count(409) == 1, f"the loser must be told the seat is taken, got {codes}"

    async with SessionLocal() as session:
        holds = list(await session.scalars(select(SeatHold)))
    assert len(holds) == 1, "only one hold may survive"


async def test_confirming_without_a_live_hold_is_refused(client, movie):
    """The backend re-checks; a client that skips the hold gets nothing."""
    user = await login(client, USER_ID)
    payload = {"movie_id": movie.id, "show_date": SHOW_DATE, "session": SESSION, "seats": ["3-1"]}
    response = await client.post(
        "/api/bookings/confirm", json={**payload, **CONTACT}, headers=auth_header(user)
    )
    assert response.status_code == 409

    async with SessionLocal() as session:
        assert list(await session.scalars(select(Booking))) == []


async def test_holding_again_replaces_my_previous_selection(client, movie):
    user = await login(client, USER_ID)
    await _hold(client, movie.id, ["1-1", "1-2"], user)
    await _hold(client, movie.id, ["3-4"], user)

    hall = await _seats(client, movie.id, user)
    assert hall["mine"] == ["3-4"], "changing the selection must release the old seats"
    assert hall["taken"] == []


async def test_concurrent_first_requests_do_not_race_on_the_settings_row(client, movie):
    """Regression: get_settings did check-then-insert on a shared id.

    On a fresh database two parallel requests both saw no settings row, both
    inserted id=1, and the loser died on the primary key with a 500 — and
    almost every endpoint calls get_settings.
    """
    async with SessionLocal() as session:
        row = await session.scalar(select(CinemaSettings))
        if row is not None:
            await session.delete(row)
            await session.commit()

    results = await asyncio.gather(
        client.get("/api/settings"),
        client.get("/api/settings"),
        client.get(f"/api/movies/{movie.id}"),
        return_exceptions=True,
    )
    for item in results:
        assert not isinstance(item, BaseException), f"first-run race raised {item!r}"
        assert item.status_code == 200, item.text

    async with SessionLocal() as session:
        rows = list(await session.scalars(select(CinemaSettings)))
    assert len(rows) == 1
