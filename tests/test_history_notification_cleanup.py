"""Users and admins can clear stale history without losing active work or audit rows."""
from datetime import timedelta

import pytest

from sqlalchemy import select

from backend.core.db import SessionLocal, utcnow
from backend.models import AdminNotification, Booking, User, UserNotification
from backend.services import booking_decisions
from tests.conftest import ADMIN_ID, OTHER_ID, USER_ID, auth_header, login
from tests.test_generic_booking import book


async def _cancel(client, token: str, booking_id: int):
    return await client.patch(
        f"/api/profile/bookings/{booking_id}/cancel", headers=auth_header(token)
    )


async def test_client_clears_only_finished_history_and_audit_row_survives(client):
    owner = await login(client, USER_ID)
    finished = await book(client, owner, 1)
    active = await book(client, owner, 1)
    assert (await _cancel(client, owner, finished["id"])).status_code == 200

    response = await client.delete("/api/profile/history/bookings", headers=auth_header(owner))

    assert response.status_code == 200, response.text
    assert response.json() == {"cleared": 1}
    visible = (await client.get("/api/profile/bookings", headers=auth_header(owner))).json()
    assert [row["id"] for row in visible] == [active["id"]]
    async with SessionLocal() as session:
        retained = await session.get(Booking, finished["id"])
    assert retained is not None and retained.status == "cancelled"
    assert retained.viewer_hidden_at is not None


async def test_old_finished_history_hides_automatically_but_fresh_history_remains(client):
    owner = await login(client, USER_ID)
    old = await book(client, owner, 1)
    fresh = await book(client, owner, 1)
    assert (await _cancel(client, owner, old["id"])).status_code == 200
    assert (await _cancel(client, owner, fresh["id"])).status_code == 200
    async with SessionLocal() as session:
        old_row = await session.get(Booking, old["id"])
        old_row.completed_at = utcnow() - timedelta(days=181)
        await session.commit()

    visible = (await client.get("/api/profile/bookings", headers=auth_header(owner))).json()

    assert [row["id"] for row in visible] == [fresh["id"]]


async def test_client_and_admin_clear_notifications_in_their_own_scope(client):
    owner = await login(client, USER_ID)
    other = await login(client, OTHER_ID)
    admin = await login(client, ADMIN_ID, "admin")
    booking = await book(client, owner, 1)
    async with SessionLocal() as session:
        owner_user = await session.scalar(select(User).where(User.telegram_id == USER_ID))
        other_user = await session.scalar(select(User).where(User.telegram_id == OTHER_ID))
        session.add_all(
            [
                UserNotification(user_id=owner_user.id, type="status", title="A", message="A"),
                UserNotification(user_id=other_user.id, type="status", title="B", message="B"),
                AdminNotification(booking_id=booking["id"], message="Admin A"),
            ]
        )
        await session.commit()

    user_response = await client.delete("/api/profile/notifications", headers=auth_header(owner))
    admin_response = await client.delete("/api/admin/notifications", headers=auth_header(admin))

    assert user_response.status_code == 200 and user_response.json()["cleared"] >= 1
    assert admin_response.status_code == 200 and admin_response.json()["cleared"] >= 1
    assert (await client.get("/api/profile/notifications", headers=auth_header(owner))).json() == []
    assert len((await client.get("/api/profile/notifications", headers=auth_header(other))).json()) == 1
    assert (await client.get("/api/admin/notifications", headers=auth_header(admin))).json() == []


async def test_old_notifications_are_pruned_with_unread_grace_period(client):
    owner = await login(client, USER_ID)
    async with SessionLocal() as session:
        user = await session.scalar(select(User).where(User.telegram_id == USER_ID))
        session.add_all(
            [
                UserNotification(
                    user_id=user.id, type="status", title="old read", message="x",
                    is_read=True, created_at=utcnow() - timedelta(days=31),
                ),
                UserNotification(
                    user_id=user.id, type="status", title="unread grace", message="x",
                    is_read=False, created_at=utcnow() - timedelta(days=31),
                ),
                UserNotification(
                    user_id=user.id, type="status", title="ancient unread", message="x",
                    is_read=False, created_at=utcnow() - timedelta(days=91),
                ),
            ]
        )
        await session.commit()

    rows = (await client.get("/api/profile/notifications", headers=auth_header(owner))).json()

    assert [row["title"] for row in rows] == ["unread grace"]


async def test_history_clear_cannot_be_overwritten_by_a_stale_admin_revival(client):
    owner = await login(client, USER_ID)
    created = await book(client, owner, 1)
    assert (await _cancel(client, owner, created["id"])).status_code == 200

    async with SessionLocal() as stale_admin_session:
        stale = await stale_admin_session.get(Booking, created["id"])
        assert stale is not None and stale.status == "cancelled"
        cleared = await client.delete("/api/profile/history/bookings", headers=auth_header(owner))
        assert cleared.status_code == 200
        with pytest.raises(booking_decisions.BookingTransitionConflict):
            await booking_decisions.apply_status(stale_admin_session, created["id"], "confirmed")

    async with SessionLocal() as session:
        current = await session.get(Booking, created["id"])
    assert current.status == "cancelled" and current.viewer_hidden_at is not None


async def test_admin_revival_makes_a_cleared_booking_visible_again(client):
    owner = await login(client, USER_ID)
    admin = await login(client, ADMIN_ID, "admin")
    created = await book(client, owner, 1)
    assert (await _cancel(client, owner, created["id"])).status_code == 200
    assert (await client.delete("/api/profile/history/bookings", headers=auth_header(owner))).status_code == 200

    revived = await client.patch(
        f"/api/admin/bookings/{created['id']}/status",
        json={"status": "confirmed"}, headers=auth_header(admin),
    )

    assert revived.status_code == 200, revived.text
    visible = (await client.get("/api/profile/bookings", headers=auth_header(owner))).json()
    assert [item["id"] for item in visible] == [created["id"]]


async def test_admin_cannot_propose_a_time_for_a_terminal_booking(client):
    owner = await login(client, USER_ID)
    admin = await login(client, ADMIN_ID, "admin")
    created = await book(client, owner, 1)
    assert (await _cancel(client, owner, created["id"])).status_code == 200

    response = await client.patch(
        f"/api/admin/bookings/{created['id']}/decision",
        json={"action": "propose", "reason": "", "proposed_session": "20:00"},
        headers=auth_header(admin),
    )

    assert response.status_code == 409
