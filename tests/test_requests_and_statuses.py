"""Stages 11-12: requests handled by the admin, and the status lifecycle.

Spec: no payment gateway of any kind; the viewer creates a request, the admin
sees it, contacts the person, settles payment outside the app and confirms or
cancels. Cancelling frees the seats, confirming locks them in.
"""
from __future__ import annotations

from sqlalchemy import select

from backend.core import config
from backend.core.db import SessionLocal
from backend.models import Booking, Show
from tests.conftest import ADMIN_ID, OTHER_ID, SESSION, SHOW_DATE, USER_ID, auth_header, login

CONTACT = {
    "first_name": "Иван",
    "last_name": "Петров",
    "phone": "+998 91 326 20 65",
    "telegram_username": "ivanp",
    "comment": "Позвоните после 18:00",
}


async def _book(client, movie_id: int, seats: list[str], token: str):
    payload = {"movie_id": movie_id, "show_date": SHOW_DATE, "session": SESSION, "seats": seats}
    await client.post("/api/holds", json=payload, headers=auth_header(token))
    return await client.post("/api/bookings/confirm", json={**payload, **CONTACT}, headers=auth_header(token))


async def _admin_rows(client, token: str):
    response = await client.get("/api/admin/bookings", headers=auth_header(token))
    assert response.status_code == 200
    return response.json()


async def _seats(client, movie_id: int):
    response = await client.get(
        f"/api/sessions/{movie_id}/seats", params={"show_date": SHOW_DATE, "session_time": SESSION}
    )
    return response.json()


# --- stage 11: the request reaches the admin, nothing is paid in the app -----


async def test_booking_creates_a_request_not_a_payment(client, movie):
    user = await login(client, USER_ID)
    response = await _book(client, movie.id, ["1-1"], user)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending"
    # Nothing that smells of an online payment may appear in the contract.
    assert not {"payment_url", "invoice", "provider", "paid"} & set(body)


async def test_admin_sees_the_request_with_everything_needed_to_call_back(client, movie):
    user = await login(client, USER_ID)
    await _book(client, movie.id, ["1-1", "1-2"], user)

    admin = await login(client, ADMIN_ID, "admin")
    row = (await _admin_rows(client, admin))[0]
    assert row["status"] == "pending"
    assert row["phone"] == "+998913262065"
    assert row["name"] == "Иван Петров"
    assert row["telegram_username"] == "ivanp"
    assert row["chat_url"] == "https://t.me/ivanp"
    assert row["comment"] == "Позвоните после 18:00"
    assert row["seats"] == "1-1,1-2"
    assert row["total"] == 60000


async def test_admin_confirms_and_the_viewer_is_told(client, movie):
    user = await login(client, USER_ID)
    await _book(client, movie.id, ["1-1"], user)
    admin = await login(client, ADMIN_ID, "admin")
    booking_id = (await _admin_rows(client, admin))[0]["id"]

    decision = await client.patch(
        f"/api/admin/bookings/{booking_id}/decision",
        json={"action": "confirm", "reason": "", "proposed_session": ""},
        headers=auth_header(admin),
    )
    assert decision.status_code == 200
    assert decision.json()["status"] == "confirmed"

    notes = (await client.get("/api/profile/notifications", headers=auth_header(user))).json()
    assert any("подтверждена" in item["message"] for item in notes)


async def test_admin_cancels_with_a_reason_and_the_viewer_is_told(client, movie):
    user = await login(client, USER_ID)
    await _book(client, movie.id, ["1-1"], user)
    admin = await login(client, ADMIN_ID, "admin")
    booking_id = (await _admin_rows(client, admin))[0]["id"]

    decision = await client.patch(
        f"/api/admin/bookings/{booking_id}/decision",
        json={"action": "decline", "reason": "зал на ремонте", "proposed_session": ""},
        headers=auth_header(admin),
    )
    assert decision.status_code == 200
    assert decision.json()["status"] == "cancelled"
    assert decision.json()["admin_note"] == "зал на ремонте"

    notes = (await client.get("/api/profile/notifications", headers=auth_header(user))).json()
    assert any("зал на ремонте" in item["message"] for item in notes)


# --- stage 12: the lifecycle ------------------------------------------------


async def test_only_the_five_spec_statuses_are_accepted(client, movie):
    user = await login(client, USER_ID)
    await _book(client, movie.id, ["1-1"], user)
    admin = await login(client, ADMIN_ID, "admin")
    booking_id = (await _admin_rows(client, admin))[0]["id"]

    assert config.BOOKING_STATUSES == ("pending", "contacting", "confirmed", "cancelled", "watched")
    for status in config.BOOKING_STATUSES:
        response = await client.patch(
            f"/api/admin/bookings/{booking_id}/status",
            json={"status": status},
            headers=auth_header(admin),
        )
        assert response.status_code == 200, f"{status} should be settable"

    for rejected in ("completed", "paid", "done", ""):
        response = await client.patch(
            f"/api/admin/bookings/{booking_id}/status",
            json={"status": rejected},
            headers=auth_header(admin),
        )
        assert response.status_code == 422, f"{rejected} must be refused"


async def test_watched_stamps_the_time_once(client, movie):
    user = await login(client, USER_ID)
    await _book(client, movie.id, ["1-1"], user)
    admin = await login(client, ADMIN_ID, "admin")
    booking_id = (await _admin_rows(client, admin))[0]["id"]

    await client.patch(
        f"/api/admin/bookings/{booking_id}/status", json={"status": "watched"}, headers=auth_header(admin)
    )
    async with SessionLocal() as session:
        first = (await session.get(Booking, booking_id)).completed_at
    assert first is not None

    await client.patch(
        f"/api/admin/bookings/{booking_id}/status", json={"status": "watched"}, headers=auth_header(admin)
    )
    async with SessionLocal() as session:
        assert (await session.get(Booking, booking_id)).completed_at == first, "must not be re-stamped"


async def test_cancelling_frees_the_seats_and_confirming_locks_them(client, movie):
    user = await login(client, USER_ID)
    await _book(client, movie.id, ["2-2"], user)
    admin = await login(client, ADMIN_ID, "admin")
    booking_id = (await _admin_rows(client, admin))[0]["id"]

    await client.patch(
        f"/api/admin/bookings/{booking_id}/status", json={"status": "confirmed"}, headers=auth_header(admin)
    )
    assert (await _seats(client, movie.id))["booked"] == ["2-2"]

    await client.patch(
        f"/api/admin/bookings/{booking_id}/status", json={"status": "cancelled"}, headers=auth_header(admin)
    )
    assert (await _seats(client, movie.id))["taken"] == []


async def test_reviving_a_cancelled_request_cannot_double_book_the_seat(client, movie):
    """Cancelling frees the seat, so restoring the request must re-check it.

    Otherwise: A books, admin cancels, B books the freed seat, admin changes
    their mind and un-cancels A — and one seat carries two live bookings.
    """
    first = await login(client, USER_ID)
    await _book(client, movie.id, ["3-3"], first)
    admin = await login(client, ADMIN_ID, "admin")
    booking_id = (await _admin_rows(client, admin))[0]["id"]

    await client.patch(
        f"/api/admin/bookings/{booking_id}/status", json={"status": "cancelled"}, headers=auth_header(admin)
    )

    second = await login(client, OTHER_ID, "other")
    assert (await _book(client, movie.id, ["3-3"], second)).status_code == 200

    revived = await client.patch(
        f"/api/admin/bookings/{booking_id}/status", json={"status": "confirmed"}, headers=auth_header(admin)
    )
    assert revived.status_code == 409, "the seat now belongs to somebody else"

    async with SessionLocal() as session:
        live = [
            booking
            for booking in await session.scalars(select(Booking))
            if booking.status in config.BLOCKING_STATUSES and "3-3" in booking.seats.split(",")
        ]
    assert len(live) == 1, f"one seat, one live booking — found {len(live)}"


async def test_reviving_is_allowed_when_the_seat_is_still_free(client, movie):
    user = await login(client, USER_ID)
    await _book(client, movie.id, ["3-4"], user)
    admin = await login(client, ADMIN_ID, "admin")
    booking_id = (await _admin_rows(client, admin))[0]["id"]

    await client.patch(
        f"/api/admin/bookings/{booking_id}/status", json={"status": "cancelled"}, headers=auth_header(admin)
    )
    revived = await client.patch(
        f"/api/admin/bookings/{booking_id}/status", json={"status": "confirmed"}, headers=auth_header(admin)
    )
    assert revived.status_code == 200
    assert (await _seats(client, movie.id))["booked"] == ["3-4"]


async def test_status_changes_are_admin_only(client, movie):
    user = await login(client, USER_ID)
    await _book(client, movie.id, ["1-1"], user)
    admin = await login(client, ADMIN_ID, "admin")
    booking_id = (await _admin_rows(client, admin))[0]["id"]

    assert (
        await client.patch(
            f"/api/admin/bookings/{booking_id}/status",
            json={"status": "confirmed"},
            headers=auth_header(user),
        )
    ).status_code == 403
    assert (
        await client.patch(
            f"/api/admin/bookings/{booking_id}/decision",
            json={"action": "confirm", "reason": "", "proposed_session": ""},
            headers=auth_header(user),
        )
    ).status_code == 403


# --- the admin's alternative time -------------------------------------------


async def _propose(client, admin_token: str, booking_id: int, time: str):
    return await client.patch(
        f"/api/admin/bookings/{booking_id}/decision",
        json={"action": "propose", "reason": "перенос", "proposed_session": time},
        headers=auth_header(admin_token),
    )


async def test_accepting_a_new_time_checks_that_the_seats_are_free_there(client, movie):
    """Moving a booking to another session must not land it on a taken seat."""
    async with SessionLocal() as session:
        session.add(Show(movie_id=movie.id, show_date=SHOW_DATE, start_time="21:30"))
        await session.commit()

    # Somebody already holds 1-1 at 21:30.
    other = await login(client, OTHER_ID, "other")
    rival = {"movie_id": movie.id, "show_date": SHOW_DATE, "session": "21:30", "seats": ["1-1"]}
    await client.post("/api/holds", json=rival, headers=auth_header(other))
    assert (
        await client.post("/api/bookings/confirm", json={**rival, **CONTACT}, headers=auth_header(other))
    ).status_code == 200

    user = await login(client, USER_ID)
    await _book(client, movie.id, ["1-1"], user)
    admin = await login(client, ADMIN_ID, "admin")
    mine = [row for row in await _admin_rows(client, admin) if row["session"] == SESSION][0]
    assert (await _propose(client, admin, mine["id"], "21:30")).status_code == 200

    accepted = await client.patch(
        f"/api/profile/bookings/{mine['id']}/proposal",
        json={"action": "accept"},
        headers=auth_header(user),
    )
    assert accepted.status_code == 409, "1-1 at 21:30 belongs to somebody else"

    async with SessionLocal() as session:
        booking = await session.get(Booking, mine["id"])
        assert booking.session == SESSION, "a refused move must not change the session"
        assert booking.proposed_session == "21:30", "the offer stays open"


async def test_accepting_a_new_time_requires_a_real_screening(client, movie):
    user = await login(client, USER_ID)
    await _book(client, movie.id, ["1-1"], user)
    admin = await login(client, ADMIN_ID, "admin")
    booking_id = (await _admin_rows(client, admin))[0]["id"]
    assert (await _propose(client, admin, booking_id, "04:15")).status_code == 200

    accepted = await client.patch(
        f"/api/profile/bookings/{booking_id}/proposal",
        json={"action": "accept"},
        headers=auth_header(user),
    )
    assert accepted.status_code == 404, "there is no screening at 04:15"


async def test_accepting_a_free_new_time_moves_the_booking(client, movie):
    async with SessionLocal() as session:
        session.add(Show(movie_id=movie.id, show_date=SHOW_DATE, start_time="21:30"))
        await session.commit()

    user = await login(client, USER_ID)
    await _book(client, movie.id, ["1-1"], user)
    admin = await login(client, ADMIN_ID, "admin")
    booking_id = (await _admin_rows(client, admin))[0]["id"]
    await _propose(client, admin, booking_id, "21:30")

    accepted = await client.patch(
        f"/api/profile/bookings/{booking_id}/proposal",
        json={"action": "accept"},
        headers=auth_header(user),
    )
    assert accepted.status_code == 200
    assert accepted.json()["session"] == "21:30"
    assert (await _seats(client, movie.id))["taken"] == [], "the old time is free again"
