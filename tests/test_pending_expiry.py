"""A request the administrator never answered must not hold the hall forever.

Payment is manual: a request sits in `pending` until somebody calls the viewer
back. Nothing ever released those places, so one forgotten request kept two of
the twelve seats out of circulation for good, and a day could quietly stop
selling without anybody noticing.

The rule is deliberately narrow. Only `pending` expires: `contacting` means the
administrator is already on the phone with that person, and confirming or
declining is their decision to make, not a timer's.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select

from backend.core.db import SessionLocal, utcnow
from backend.models import Booking
from backend.services.requests import expire_stale_requests
from tests.conftest import ADMIN_ID, OTHER_ID, SHOW_DATE, USER_ID, auth_header, login
from tests.test_generic_booking import available, book

SLOT = "18:00"


async def age_request(booking_id: int, hours: float) -> None:
    """Backdate a request so it looks like it has been waiting that long."""
    async with SessionLocal() as session:
        booking = await session.get(Booking, booking_id)
        booking.created_at = utcnow() - timedelta(hours=hours)
        await session.commit()


async def status_of(booking_id: int) -> str:
    async with SessionLocal() as session:
        return (await session.get(Booking, booking_id)).status


async def set_expiry(client, hours: int) -> None:
    admin = await login(client, ADMIN_ID, "admin")
    current = (await client.get("/api/admin/settings", headers=auth_header(admin))).json()
    current["pending_expire_hours"] = hours
    response = await client.put("/api/admin/settings", json=current, headers=auth_header(admin))
    assert response.status_code == 200, response.text


# --- the places come back -----------------------------------------------------


async def test_a_forgotten_request_stops_holding_the_hall(client):
    token = await login(client, USER_ID)
    booking = await book(client, token, 12)
    assert await available(client) == 0

    await age_request(booking["id"], hours=48)
    assert await available(client) == 12, "a request nobody answered cannot hold the hall for ever"


async def test_somebody_else_can_book_the_freed_places(client):
    first = await login(client, USER_ID)
    booking = await book(client, first, 12)
    await age_request(booking["id"], hours=48)

    second = await login(client, OTHER_ID, "other")
    taken = await book(client, second, 12)
    assert taken["party_size"] == 12


async def test_a_fresh_request_still_holds_its_places(client):
    token = await login(client, USER_ID)
    await book(client, token, 12)
    await expire_stale_requests_now()
    assert await available(client) == 0, "a request made an hour ago is not stale"


async def expire_stale_requests_now() -> int:
    async with SessionLocal() as session:
        expired = await expire_stale_requests(session)
        await session.commit()
        return expired


# --- only pending, and only when the admin asked for it -----------------------


async def test_a_request_the_admin_is_working_on_never_expires(client):
    """`contacting` means somebody is on the phone with that viewer."""
    user = await login(client, USER_ID)
    booking = await book(client, user, 4)
    admin = await login(client, ADMIN_ID, "admin")
    moved = await client.patch(
        f"/api/admin/bookings/{booking['id']}/decision",
        json={"action": "contact", "reason": "", "proposed_session": ""},
        headers=auth_header(admin),
    )
    assert moved.status_code == 200

    await age_request(booking["id"], hours=240)
    await expire_stale_requests_now()
    assert await status_of(booking["id"]) == "contacting"


async def test_a_confirmed_request_never_expires(client):
    user = await login(client, USER_ID)
    booking = await book(client, user, 4)
    admin = await login(client, ADMIN_ID, "admin")
    await client.patch(
        f"/api/admin/bookings/{booking['id']}/decision",
        json={"action": "confirm", "reason": "", "proposed_session": ""},
        headers=auth_header(admin),
    )

    await age_request(booking["id"], hours=240)
    await expire_stale_requests_now()
    assert await status_of(booking["id"]) == "confirmed"
    assert await available(client) == 8, "a paid-for evening is not given away by a timer"


async def test_expiry_can_be_switched_off(client):
    await set_expiry(client, 0)
    token = await login(client, USER_ID)
    booking = await book(client, token, 12)
    await age_request(booking["id"], hours=1000)

    await expire_stale_requests_now()
    assert await status_of(booking["id"]) == "pending"
    assert await available(client) == 0


async def test_the_admin_sets_how_long_a_request_may_wait(client):
    await set_expiry(client, 3)
    token = await login(client, USER_ID)
    booking = await book(client, token, 6)

    await age_request(booking["id"], hours=2)
    await expire_stale_requests_now()
    assert await status_of(booking["id"]) == "pending", "two hours is inside the three-hour window"

    await age_request(booking["id"], hours=4)
    await expire_stale_requests_now()
    assert await status_of(booking["id"]) == "cancelled"


# --- what the viewer and the administrator see --------------------------------


async def test_an_expired_request_says_why_it_was_cancelled(client):
    token = await login(client, USER_ID)
    booking = await book(client, token, 2)
    await age_request(booking["id"], hours=48)
    await expire_stale_requests_now()

    async with SessionLocal() as session:
        row = await session.get(Booking, booking["id"])
    assert row.status == "cancelled"
    assert row.admin_note, "a request that vanished without a word is worse than the bug"

    listed = (await client.get("/api/profile/bookings", headers=auth_header(token))).json()
    mine = next(item for item in listed if item["id"] == booking["id"])
    assert mine["status"] == "cancelled"
    assert mine["admin_note"] == row.admin_note


async def test_the_request_is_kept_rather_than_deleted(client):
    """History stays: the QR, the code and the contacts are still on the row."""
    token = await login(client, USER_ID)
    booking = await book(client, token, 2)
    await age_request(booking["id"], hours=48)
    await expire_stale_requests_now()

    async with SessionLocal() as session:
        rows = list(await session.scalars(select(Booking)))
    assert len(rows) == 1
    assert rows[0].uuid and rows[0].qr_token and rows[0].phone


async def test_expiring_is_idempotent(client):
    token = await login(client, USER_ID)
    booking = await book(client, token, 3)
    await age_request(booking["id"], hours=48)

    assert await expire_stale_requests_now() == 1
    assert await expire_stale_requests_now() == 0, "an already-cancelled request is not expired twice"
