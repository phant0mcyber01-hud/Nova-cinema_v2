"""Phase A: booking places in the hall, with no film and no chosen chair.

The viewer names a date, one of the fixed times and how many people are coming.
The backend allocates the capacity itself, freezes `base_ticket_price * party_size`
and files a request the administrator will phone back about.  Payment happens
outside the app, so nothing here ever reaches a `paid` state.
"""
from __future__ import annotations

import asyncio

from sqlalchemy import select

from backend.core.db import SessionLocal
from backend.models import Booking, CapacityHold
from tests.conftest import (
    ADMIN_ID,
    OTHER_ID,
    SHOW_DATE,
    USER_ID,
    auth_header,
    login,
)

SLOT = "18:00"
CONTACT = {
    "first_name": "Иван",
    "last_name": "Петров",
    "phone": "+998 91 326 20 65",
    "telegram_username": "ivanp",
    "comment": "",
}


async def hold(client, token: str, party_size: int, time: str = SLOT, date: str = SHOW_DATE):
    return await client.post(
        "/api/booking/holds",
        json={"date": date, "time": time, "party_size": party_size},
        headers=auth_header(token),
    )


async def request_booking(
    client, token: str, party_size: int, time: str = SLOT, date: str = SHOW_DATE, **extra
):
    payload = {"date": date, "time": time, "party_size": party_size, **CONTACT, **extra}
    return await client.post("/api/booking/requests", json=payload, headers=auth_header(token))


async def book(client, token: str, party_size: int, time: str = SLOT, date: str = SHOW_DATE):
    assert (await hold(client, token, party_size, time, date)).status_code == 200
    response = await request_booking(client, token, party_size, time, date)
    assert response.status_code == 200, response.text
    return response.json()


async def available(client, time: str = SLOT, date: str = SHOW_DATE) -> int:
    body = (await client.get("/api/booking/slots", params={"date": date})).json()
    return next(slot["available"] for slot in body["slots"] if slot["time"] == time)


async def legacy_booking(user_id: int, movie_id: int | None, party_size: int, time: str = SLOT):
    """A movie-bound request written straight to the database.

    The legacy flow is what the app looked like before Phase A; these rows still
    occupy the one physical hall.
    """
    async with SessionLocal() as session:
        booking = Booking(
            user_id=user_id,
            movie_id=movie_id,
            show_date=SHOW_DATE,
            session=time,
            seats=",".join(f"1-{index + 1}" for index in range(party_size)),
            party_size=party_size,
            status="pending",
            ticket_price=30000,
            total=30000 * party_size,
            code=str(user_id),
        )
        session.add(booking)
        await session.commit()
        return booking.id


# --- the request itself ------------------------------------------------------


async def test_a_request_needs_no_movie_at_all(client):
    token = await login(client, USER_ID)
    body = await book(client, token, 3)
    assert body["status"] == "pending"
    assert body["party_size"] == 3
    assert "movie_id" not in body and "movie" not in body

    async with SessionLocal() as session:
        booking = await session.scalar(select(Booking))
    assert booking.movie_id is None, "the mini app does not book a film"
    assert booking.party_size == 3
    assert booking.show_date == SHOW_DATE
    assert booking.session == SLOT


async def test_the_total_is_the_base_price_times_the_party(client):
    token = await login(client, USER_ID)
    body = await book(client, token, 4)
    assert body["ticket_price"] == 30000
    assert body["total"] == 120000


async def test_the_client_cannot_name_its_own_price(client):
    """A payload carrying a price is ignored: the server owns the formula."""
    token = await login(client, USER_ID)
    assert (await hold(client, token, 2)).status_code == 200
    response = await request_booking(
        client, token, 2, ticket_price=1, total=2, price=1, base_ticket_price=1
    )
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 60000

    async with SessionLocal() as session:
        booking = await session.scalar(select(Booking))
    assert (booking.ticket_price, booking.total) == (30000, 60000)


async def test_the_frozen_price_survives_a_later_change(client):
    user = await login(client, USER_ID)
    first = await book(client, user, 1)
    assert first["total"] == 30000

    admin = await login(client, ADMIN_ID, "admin")
    changed = await client.patch(
        "/api/admin/settings/base-price",
        json={"base_ticket_price": 35000},
        headers=auth_header(admin),
    )
    assert changed.status_code == 200
    second = await book(client, user, 1, time="20:00")
    assert second["total"] == 35000

    async with SessionLocal() as session:
        rows = list(await session.scalars(select(Booking).order_by(Booking.id)))
    assert [row.total for row in rows] == [30000, 35000]


async def test_payment_is_manual_so_the_request_only_ever_starts_pending(client):
    token = await login(client, USER_ID)
    body = await book(client, token, 2)
    assert body["status"] == "pending"
    assert "payment_url" not in body and "paid" not in body


async def test_a_request_without_a_live_hold_is_refused(client):
    token = await login(client, USER_ID)
    response = await request_booking(client, token, 2)
    assert response.status_code == 409

    async with SessionLocal() as session:
        assert list(await session.scalars(select(Booking))) == []


async def test_a_request_for_more_people_than_were_held_is_refused(client):
    token = await login(client, USER_ID)
    assert (await hold(client, token, 2)).status_code == 200
    assert (await request_booking(client, token, 4)).status_code == 409


async def test_filing_the_request_consumes_the_hold(client):
    token = await login(client, USER_ID)
    await book(client, token, 2)
    async with SessionLocal() as session:
        assert list(await session.scalars(select(CapacityHold))) == []


# --- automatic allocation ----------------------------------------------------


async def test_the_viewer_picks_a_number_and_the_backend_picks_the_places(client):
    token = await login(client, USER_ID)
    response = await hold(client, token, 3)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["party_size"] == 3
    assert "seats" not in body and "token" not in body and "tokens" not in body

    async with SessionLocal() as session:
        held = sorted(item.token for item in await session.scalars(select(CapacityHold)))
    assert held == [1, 2, 3], "capacity is allocated internally, lowest token first"


async def test_two_parties_get_disjoint_places(client):
    first = await login(client, USER_ID)
    second = await login(client, OTHER_ID, "other")
    assert (await hold(client, first, 4)).status_code == 200
    assert (await hold(client, second, 5)).status_code == 200

    async with SessionLocal() as session:
        rows = list(await session.scalars(select(CapacityHold)))
    assert len({item.token for item in rows}) == 9, "no place may be handed out twice"


async def test_holding_again_replaces_the_previous_selection(client):
    token = await login(client, USER_ID)
    await hold(client, token, 5)
    assert (await hold(client, token, 2)).status_code == 200

    async with SessionLocal() as session:
        rows = list(await session.scalars(select(CapacityHold)))
    assert len(rows) == 2
    assert await available(client) == 10


async def test_releasing_a_hold_gives_the_places_back(client):
    token = await login(client, USER_ID)
    await hold(client, token, 6)
    released = await client.delete(
        "/api/booking/holds",
        params={"date": SHOW_DATE, "time": SLOT},
        headers=auth_header(token),
    )
    assert released.status_code == 200
    assert await available(client) == 12


async def test_my_own_hold_does_not_block_me(client):
    token = await login(client, USER_ID)
    await hold(client, token, 4)
    body = (
        await client.get(
            "/api/booking/slots", params={"date": SHOW_DATE}, headers=auth_header(token)
        )
    ).json()
    slot = next(item for item in body["slots"] if item["time"] == SLOT)
    assert slot["mine"] == 4
    assert slot["available"] == 12, "my own hold must still be mine to confirm"


# --- the twelve-place ceiling ------------------------------------------------


async def test_a_party_larger_than_the_hall_is_refused(client):
    token = await login(client, USER_ID)
    assert (await hold(client, token, 13)).status_code == 422


async def test_the_whole_hall_can_be_taken_by_one_party(client):
    token = await login(client, USER_ID)
    body = await book(client, token, 12)
    assert body["total"] == 360000
    assert await available(client) == 0


async def test_the_thirteenth_place_cannot_be_sold(client):
    first = await login(client, USER_ID)
    await book(client, first, 12)

    second = await login(client, OTHER_ID, "other")
    clash = await hold(client, second, 1)
    assert clash.status_code == 409


async def test_a_full_slot_does_not_close_the_other_times(client):
    token = await login(client, USER_ID)
    await book(client, token, 12)
    assert await available(client, "20:00") == 12


# --- one physical hall, whatever film anyone agreed --------------------------


async def test_a_movie_bound_booking_eats_the_same_hall(client, movie):
    """The old flow reserved seats per film; the hall never worked that way."""
    await legacy_booking(1, movie.id, 5)
    assert await available(client) == 7


async def test_two_different_films_at_one_time_share_the_twelve_places(client, movie):
    async with SessionLocal() as session:
        from tests.conftest import movie_row

        other = movie_row("Второй фильм")
        session.add(other)
        await session.commit()
        other_id = other.id

    await legacy_booking(1, movie.id, 6)
    await legacy_booking(1, other_id, 6)
    assert await available(client) == 0, "capacity is the hall, never the film"

    token = await login(client, USER_ID)
    assert (await hold(client, token, 1)).status_code == 409


async def test_the_legacy_flow_cannot_oversell_a_hall_the_generic_flow_filled(client, movie):
    """A movie-bound hold must respect places already taken for that hour."""
    async with SessionLocal() as session:
        from backend.models import Show

        session.add(Show(movie_id=movie.id, show_date=SHOW_DATE, start_time=SLOT))
        await session.commit()

    token = await login(client, USER_ID)
    await book(client, token, 12)

    other = await login(client, OTHER_ID, "other")
    clash = await client.post(
        "/api/holds",
        json={"movie_id": movie.id, "show_date": SHOW_DATE, "session": SLOT, "seats": ["3-1"]},
        headers=auth_header(other),
    )
    assert clash.status_code == 409


# --- races -------------------------------------------------------------------


async def test_two_parties_racing_for_the_whole_hall_leave_one_winner(client):
    """The unique key arbitrates; the loser is told, never handed a 500."""
    first = await login(client, USER_ID)
    second = await login(client, OTHER_ID, "other")

    results = await asyncio.gather(
        hold(client, first, 12), hold(client, second, 12), return_exceptions=True
    )
    codes = sorted(item.status_code for item in results if not isinstance(item, BaseException))
    assert 500 not in codes, f"a race must not surface as a server error: {codes}"
    assert codes.count(200) == 1, f"exactly one party may take the hall, got {codes}"
    assert codes.count(409) == 1, f"the loser must be told, got {codes}"

    async with SessionLocal() as session:
        rows = list(await session.scalars(select(CapacityHold)))
    assert len(rows) == 12, "only one allocation may survive"


async def test_a_race_for_seven_places_each_cannot_seat_fourteen(client):
    first = await login(client, USER_ID)
    second = await login(client, OTHER_ID, "other")

    results = await asyncio.gather(
        hold(client, first, 7), hold(client, second, 7), return_exceptions=True
    )
    codes = sorted(item.status_code for item in results if not isinstance(item, BaseException))
    assert 500 not in codes, codes
    assert codes.count(200) == 1, f"twelve places cannot hold fourteen people, got {codes}"

    async with SessionLocal() as session:
        rows = list(await session.scalars(select(CapacityHold)))
    assert len(rows) == 7


# --- the administrator's decisions -------------------------------------------


async def _decide(client, admin: str, booking_id: int, action: str, **extra):
    return await client.patch(
        f"/api/admin/bookings/{booking_id}/decision",
        json={"action": action, "reason": "", "proposed_session": "", **extra},
        headers=auth_header(admin),
    )


async def test_cancelling_frees_the_places(client):
    user = await login(client, USER_ID)
    booking = await book(client, user, 12)
    admin = await login(client, ADMIN_ID, "admin")
    assert (await _decide(client, admin, booking["id"], "decline")).status_code == 200
    assert await available(client) == 12


async def test_pending_contacting_and_confirmed_all_hold_the_places(client):
    user = await login(client, USER_ID)
    booking = await book(client, user, 12)
    admin = await login(client, ADMIN_ID, "admin")
    assert await available(client) == 0
    assert (await _decide(client, admin, booking["id"], "contact")).status_code == 200
    assert await available(client) == 0
    assert (await _decide(client, admin, booking["id"], "confirm")).status_code == 200
    assert await available(client) == 0


async def test_reviving_a_cancelled_request_rechecks_the_hall(client):
    user = await login(client, USER_ID)
    booking = await book(client, user, 12)
    admin = await login(client, ADMIN_ID, "admin")
    await _decide(client, admin, booking["id"], "decline")

    other = await login(client, OTHER_ID, "other")
    await book(client, other, 12)

    revived = await client.patch(
        f"/api/admin/bookings/{booking['id']}/status",
        json={"status": "confirmed"},
        headers=auth_header(admin),
    )
    assert revived.status_code == 409, "the places went to somebody else"


async def test_a_revival_that_still_fits_is_allowed(client):
    user = await login(client, USER_ID)
    booking = await book(client, user, 4)
    admin = await login(client, ADMIN_ID, "admin")
    await _decide(client, admin, booking["id"], "decline")

    revived = await client.patch(
        f"/api/admin/bookings/{booking['id']}/status",
        json={"status": "confirmed"},
        headers=auth_header(admin),
    )
    assert revived.status_code == 200


async def test_accepting_a_proposed_time_rechecks_the_new_slot(client):
    user = await login(client, USER_ID)
    booking = await book(client, user, 12)
    admin = await login(client, ADMIN_ID, "admin")
    assert (
        await _decide(client, admin, booking["id"], "propose", proposed_session="20:00")
    ).status_code == 200

    other = await login(client, OTHER_ID, "other")
    await book(client, other, 12, time="20:00")

    moved = await client.patch(
        f"/api/profile/bookings/{booking['id']}/proposal",
        json={"action": "accept"},
        headers=auth_header(user),
    )
    assert moved.status_code == 409, "20:00 filled up while the offer was open"


async def test_accepting_a_proposed_time_that_still_fits_moves_the_request(client):
    user = await login(client, USER_ID)
    booking = await book(client, user, 12)
    admin = await login(client, ADMIN_ID, "admin")
    await _decide(client, admin, booking["id"], "propose", proposed_session="20:00")

    moved = await client.patch(
        f"/api/profile/bookings/{booking['id']}/proposal",
        json={"action": "accept"},
        headers=auth_header(user),
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["session"] == "20:00"
    assert await available(client) == 12
    assert await available(client, "20:00") == 0


async def test_a_watched_request_still_holds_its_places(client):
    """The evening is over but the seats were used; the slot is not free again."""
    user = await login(client, USER_ID)
    booking = await book(client, user, 12)
    admin = await login(client, ADMIN_ID, "admin")
    watched = await client.patch(
        f"/api/admin/bookings/{booking['id']}/status",
        json={"status": "watched"},
        headers=auth_header(admin),
    )
    assert watched.status_code == 200
    assert await available(client) == 0


async def test_a_live_hold_by_somebody_else_already_blocks_the_places(client):
    first = await login(client, USER_ID)
    assert (await hold(client, first, 12)).status_code == 200
    assert await available(client) == 0

    second = await login(client, OTHER_ID, "other")
    assert (await hold(client, second, 1)).status_code == 409


# --- the date list -----------------------------------------------------------


async def test_the_date_list_reports_how_full_each_day_is(client):
    token = await login(client, USER_ID)
    await book(client, token, 12)

    body = (await client.get("/api/booking/dates")).json()
    day = next(item for item in body["dates"] if item["date"] == SHOW_DATE)
    assert day["slots"] == 4, "one of the five times is now full"
    assert day["available"] == 12, "the other times are untouched"


async def test_a_day_with_every_time_taken_offers_no_slots(client):
    token = await login(client, USER_ID)
    for slot_time in ("12:00", "14:00", "16:00", "18:00", "20:00"):
        await book(client, token, 12, time=slot_time)

    body = (await client.get("/api/booking/dates")).json()
    day = next(item for item in body["dates"] if item["date"] == SHOW_DATE)
    assert (day["slots"], day["available"]) == (0, 0)
