"""A viewer can cancel their own active booking without deleting its history."""
import asyncio

import pytest
from sqlalchemy import select

import backend.api.routers.profile as profile_router
from backend.core.db import SessionLocal
from backend.models import AdminNotification, Booking
from backend.services import booking_decisions
from tests.conftest import ADMIN_ID, OTHER_ID, USER_ID, auth_header, login
from tests.test_generic_booking import available, book


async def _cancel(client, token: str, booking_id: int):
    return await client.patch(
        f"/api/profile/bookings/{booking_id}/cancel",
        headers=auth_header(token),
    )


async def test_owner_cancels_pending_booking_and_releases_the_places(client, telegram_outbox):
    owner = await login(client, USER_ID)
    free_before = await available(client)
    created = await book(client, owner, 3)
    assert await available(client) == free_before - 3
    telegram_outbox.clear()

    response = await _cancel(client, owner, created["id"])

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "cancelled"
    assert await available(client) == free_before
    history = (await client.get("/api/profile/bookings", headers=auth_header(owner))).json()
    assert history[0]["id"] == created["id"]
    assert history[0]["status"] == "cancelled", "cancellation is retained in history, not hard-deleted"
    assert history[0]["qr_valid"] is False
    assert any("отменил" in text.lower() for text in telegram_outbox.texts())
    async with SessionLocal() as session:
        notice = await session.scalar(
            select(AdminNotification).where(
                AdminNotification.booking_id == created["id"],
                AdminNotification.message.contains("отменил"),
            )
        )
    assert notice is not None and "отменил" in notice.message.lower()


async def test_owner_can_cancel_a_confirmed_booking_before_it_starts(client):
    owner = await login(client, USER_ID)
    created = await book(client, owner, 2)
    admin = await login(client, ADMIN_ID, "admin")
    confirmed = await client.patch(
        f"/api/admin/bookings/{created['id']}/decision",
        json={"action": "confirm", "reason": "", "proposed_session": ""},
        headers=auth_header(admin),
    )
    assert confirmed.status_code == 200, confirmed.text

    response = await _cancel(client, owner, created["id"])

    assert response.status_code == 200, response.text
    detail = (await client.get(f"/api/profile/bookings/{created['id']}", headers=auth_header(owner))).json()
    assert detail["status"] == "cancelled"
    assert detail["qr_valid"] is False


async def test_a_viewer_cannot_cancel_somebody_elses_booking(client):
    owner = await login(client, USER_ID)
    intruder = await login(client, OTHER_ID)
    created = await book(client, owner, 2)
    free_after_booking = await available(client)

    response = await _cancel(client, intruder, created["id"])

    assert response.status_code == 404
    assert await available(client) == free_after_booking
    async with SessionLocal() as session:
        booking = await session.get(Booking, created["id"])
    assert booking.status == "pending"


async def test_a_finished_booking_cannot_be_cancelled(client):
    owner = await login(client, USER_ID)
    created = await book(client, owner, 1)
    admin = await login(client, ADMIN_ID, "admin")
    watched = await client.patch(
        f"/api/admin/bookings/{created['id']}/status",
        json={"status": "watched"},
        headers=auth_header(admin),
    )
    assert watched.status_code == 200, watched.text

    response = await _cancel(client, owner, created["id"])

    assert response.status_code == 409
    detail = (await client.get(f"/api/profile/bookings/{created['id']}", headers=auth_header(owner))).json()
    assert detail["status"] == "watched"


async def test_two_simultaneous_cancellations_are_one_idempotent_transition(
    client, telegram_outbox, monkeypatch
):
    """SQLite ignores SELECT FOR UPDATE; both requests must not notify twice."""
    owner = await login(client, USER_ID)
    created = await book(client, owner, 2)
    telegram_outbox.clear()
    original_get_settings = profile_router.get_settings
    both_loaded = asyncio.Event()
    arrived = 0

    async def synchronize_after_booking_load(session):
        nonlocal arrived
        settings = await original_get_settings(session)
        arrived += 1
        if arrived == 2:
            both_loaded.set()
        await asyncio.wait_for(both_loaded.wait(), timeout=2)
        return settings

    monkeypatch.setattr(profile_router, "get_settings", synchronize_after_booking_load)
    responses = await asyncio.gather(
        _cancel(client, owner, created["id"]),
        _cancel(client, owner, created["id"]),
    )

    assert [response.status_code for response in responses] == [200, 200]
    async with SessionLocal() as session:
        notifications = list(
            await session.scalars(
                select(AdminNotification).where(
                    AdminNotification.booking_id == created["id"],
                    AdminNotification.message.contains("отменил"),
                )
            )
        )
    assert len(notifications) == 1
    assert sum("отменил" in text.lower() for text in telegram_outbox.texts()) == 1


async def test_a_stale_admin_writer_cannot_overwrite_a_client_cancellation(client):
    owner = await login(client, USER_ID)
    created = await book(client, owner, 1)

    async with SessionLocal() as stale_admin_session:
        stale = await stale_admin_session.get(Booking, created["id"])
        assert stale is not None and stale.status == "pending"
        assert (await _cancel(client, owner, created["id"])).status_code == 200

        with pytest.raises(booking_decisions.BookingTransitionConflict):
            await booking_decisions.apply_status(
                stale_admin_session, created["id"], "confirmed"
            )

    async with SessionLocal() as session:
        booking = await session.get(Booking, created["id"])
    assert booking.status == "cancelled"
