"""Phase A: the booking resource is the hall, not a film.

A slot is a date plus one of the administrator's fixed times.  Nothing here
mentions a movie: the schedule the viewer books against is owned by the cinema,
and which film is actually shown is agreed with the administrator afterwards.
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from backend.core.db import SessionLocal
from tests.conftest import (
    ADMIN_ID,
    SHOW_DATE,
    TODAY,
    USER_ID,
    YESTERDAY,
    auth_header,
    cinema_today,
    login,
)

DEFAULT_TIMES = ["12:00", "14:00", "16:00", "18:00", "20:00"]


# --- the fixed times ---------------------------------------------------------


async def test_the_five_fixed_times_are_the_default_schedule(client):
    """12:00, 14:00, 16:00, 18:00 and 20:00, exactly — no film required."""
    response = await client.get("/api/booking/slots", params={"date": SHOW_DATE})
    assert response.status_code == 200, response.text
    body = response.json()
    assert [slot["time"] for slot in body["slots"]] == DEFAULT_TIMES


async def test_slots_do_not_depend_on_any_movie_or_show(client):
    """No `shows` row, no published film, and the day is still bookable."""
    from backend.models import Movie, Show

    async with SessionLocal() as session:
        assert list(await session.scalars(select(Movie))) == []
        assert list(await session.scalars(select(Show))) == []

    body = (await client.get("/api/booking/slots", params={"date": SHOW_DATE})).json()
    assert len(body["slots"]) == 5


async def test_a_time_the_admin_never_configured_cannot_be_held(client):
    token = await login(client, USER_ID)
    response = await client.post(
        "/api/booking/holds",
        json={"date": SHOW_DATE, "time": "13:37", "party_size": 1},
        headers=auth_header(token),
    )
    assert response.status_code == 404


async def test_the_admin_owns_the_times_without_touching_a_film(client):
    admin = await login(client, ADMIN_ID, "admin")
    listing = await client.get("/api/admin/slots", headers=auth_header(admin))
    assert listing.status_code == 200, listing.text
    assert [item["start_time"] for item in listing.json()] == DEFAULT_TIMES
    assert all("movie_id" not in item for item in listing.json())

    created = await client.post(
        "/api/admin/slots",
        json={"start_time": "22:00", "is_active": True, "sort_order": 9},
        headers=auth_header(admin),
    )
    assert created.status_code == 200, created.text

    body = (await client.get("/api/booking/slots", params={"date": SHOW_DATE})).json()
    assert [slot["time"] for slot in body["slots"]] == DEFAULT_TIMES + ["22:00"]


async def test_a_deactivated_time_disappears_from_the_public_slots(client):
    admin = await login(client, ADMIN_ID, "admin")
    slots = (await client.get("/api/admin/slots", headers=auth_header(admin))).json()
    noon = next(item for item in slots if item["start_time"] == "12:00")

    patched = await client.patch(
        f"/api/admin/slots/{noon['id']}",
        json={"start_time": "12:00", "is_active": False, "sort_order": 0},
        headers=auth_header(admin),
    )
    assert patched.status_code == 200, patched.text

    body = (await client.get("/api/booking/slots", params={"date": SHOW_DATE})).json()
    assert [slot["time"] for slot in body["slots"]] == DEFAULT_TIMES[1:]


async def test_a_slot_time_can_be_deleted(client):
    admin = await login(client, ADMIN_ID, "admin")
    slots = (await client.get("/api/admin/slots", headers=auth_header(admin))).json()
    last = next(item for item in slots if item["start_time"] == "20:00")
    removed = await client.delete(f"/api/admin/slots/{last['id']}", headers=auth_header(admin))
    assert removed.status_code == 200, removed.text

    body = (await client.get("/api/booking/slots", params={"date": SHOW_DATE})).json()
    assert [slot["time"] for slot in body["slots"]] == DEFAULT_TIMES[:-1]


async def test_the_same_time_cannot_be_configured_twice(client):
    admin = await login(client, ADMIN_ID, "admin")
    clash = await client.post(
        "/api/admin/slots",
        json={"start_time": "12:00", "is_active": True, "sort_order": 0},
        headers=auth_header(admin),
    )
    assert clash.status_code == 409


async def test_slot_management_is_admin_only(client):
    user = await login(client, USER_ID)
    assert (await client.get("/api/admin/slots")).status_code == 401
    assert (await client.get("/api/admin/slots", headers=auth_header(user))).status_code == 403


# --- the booking window ------------------------------------------------------


async def test_the_dates_endpoint_covers_the_configured_window(client):
    response = await client.get("/api/booking/dates")
    assert response.status_code == 200, response.text
    body = response.json()
    expected = [(cinema_today() + timedelta(days=offset)).isoformat() for offset in range(7)]
    assert [item["date"] for item in body["dates"]] == expected
    assert body["capacity"] == 12
    assert body["price"] == 30000
    assert body["currency"] == "UZS"
    assert body["max_party_size"] == 12


async def test_a_past_date_is_refused(client):
    assert (await client.get("/api/booking/slots", params={"date": YESTERDAY})).status_code == 404


async def test_a_date_beyond_the_window_is_refused(client):
    far = (cinema_today() + timedelta(days=30)).isoformat()
    assert (await client.get("/api/booking/slots", params={"date": far})).status_code == 404


async def test_a_time_that_already_started_today_is_not_offered(client, cinema_clock):
    """It is noon at the cinema; 12:00 has begun and the evening has not."""
    body = (await client.get("/api/booking/slots", params={"date": TODAY})).json()
    assert [slot["time"] for slot in body["slots"]] == ["14:00", "16:00", "18:00", "20:00"]


async def test_holding_a_time_that_already_started_is_refused(client, cinema_clock):
    token = await login(client, USER_ID)
    response = await client.post(
        "/api/booking/holds",
        json={"date": TODAY, "time": "12:00", "party_size": 1},
        headers=auth_header(token),
    )
    assert response.status_code == 404


async def test_holding_on_a_past_date_is_refused(client):
    token = await login(client, USER_ID)
    response = await client.post(
        "/api/booking/holds",
        json={"date": YESTERDAY, "time": "18:00", "party_size": 1},
        headers=auth_header(token),
    )
    assert response.status_code == 404
