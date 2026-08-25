"""The critical path: auth -> catalog -> seats -> hold -> request -> admin decision -> history."""
from __future__ import annotations

import pytest

from tests.conftest import (
    ADMIN_ID,
    OTHER_ID,
    SESSION,
    SHOW_DATE,
    USER_ID,
    auth_header,
    login,
    telegram_init_data,
)

CONTACT = {
    "first_name": "Иван",
    "last_name": "Петров",
    "phone": "+998 91 326 20 65",
    "telegram_username": "ivanp",
    "comment": "",
}


async def test_auth_creates_user_and_assigns_roles(client):
    response = await client.post("/api/auth/telegram", json={"init_data": telegram_init_data(USER_ID)})
    assert response.status_code == 200
    assert response.json()["user"]["role"] == "user"

    admin_token = await login(client, ADMIN_ID, "admin")
    profile = await client.get("/api/profile", headers=auth_header(admin_token))
    assert profile.json()["telegram_id"] == ADMIN_ID


async def test_auth_rejects_forged_init_data(client):
    response = await client.post("/api/auth/telegram", json={"init_data": "auth_date=1&user=%7B%7D&hash=deadbeef"})
    assert response.status_code == 401


async def test_catalog_lists_published_movie(client, movie):
    response = await client.get("/api/movies")
    assert response.status_code == 200
    titles = [item["title"] for item in response.json()]
    assert movie.title in titles


async def test_hall_geometry_is_three_by_four(client, movie):
    response = await client.get(
        f"/api/sessions/{movie.id}/seats", params={"show_date": SHOW_DATE, "session_time": SESSION}
    )
    assert response.status_code == 200
    hall = response.json()
    assert (hall["rows"], hall["cols"], hall["seats_count"]) == (3, 4, 12)
    assert hall["max_seats"] == 4
    assert hall["price"] == 30000
    assert hall["currency"] == "UZS"
    assert hall["taken"] == []


async def test_full_booking_path(client, movie):
    token = await login(client, USER_ID)
    payload = {"movie_id": movie.id, "show_date": SHOW_DATE, "session": SESSION, "seats": ["1-1", "1-2"]}

    hold = await client.post("/api/holds", json=payload, headers=auth_header(token))
    assert hold.status_code == 200, hold.text
    assert hold.json()["total"] == 60000

    confirm = await client.post(
        "/api/bookings/confirm", json={**payload, **CONTACT}, headers=auth_header(token)
    )
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["status"] == "pending"
    assert confirm.json()["total"] == 60000

    seats = await client.get(
        f"/api/sessions/{movie.id}/seats", params={"show_date": SHOW_DATE, "session_time": SESSION}
    )
    assert seats.json()["taken"] == ["1-1", "1-2"]

    admin_token = await login(client, ADMIN_ID, "admin")
    listing = await client.get("/api/admin/bookings", headers=auth_header(admin_token))
    assert listing.status_code == 200
    booking_id = listing.json()[0]["id"]

    decision = await client.patch(
        f"/api/admin/bookings/{booking_id}/decision",
        json={"action": "confirm", "reason": "", "proposed_session": ""},
        headers=auth_header(admin_token),
    )
    assert decision.status_code == 200
    assert decision.json()["status"] == "confirmed"

    history = await client.get("/api/profile/bookings", headers=auth_header(token))
    assert history.status_code == 200
    entry = history.json()[0]
    assert entry["status"] == "confirmed"
    assert entry["seats"] == "1-1,1-2"
    assert entry["ticket_price"] == 30000
    assert entry["qr_valid"] is True


async def test_seat_held_by_another_user_conflicts(client, movie):
    first = await login(client, USER_ID)
    second = await login(client, OTHER_ID, "other")
    payload = {"movie_id": movie.id, "show_date": SHOW_DATE, "session": SESSION, "seats": ["2-3"]}

    assert (await client.post("/api/holds", json=payload, headers=auth_header(first))).status_code == 200
    clash = await client.post("/api/holds", json=payload, headers=auth_header(second))
    assert clash.status_code == 409


async def test_seat_outside_the_hall_is_rejected(client, movie):
    token = await login(client, USER_ID)
    payload = {"movie_id": movie.id, "show_date": SHOW_DATE, "session": SESSION, "seats": ["4-1"]}
    response = await client.post("/api/holds", json=payload, headers=auth_header(token))
    assert response.status_code == 422


async def test_confirm_without_hold_is_rejected(client, movie):
    token = await login(client, USER_ID)
    payload = {"movie_id": movie.id, "show_date": SHOW_DATE, "session": SESSION, "seats": ["3-5"]}
    response = await client.post(
        "/api/bookings/confirm", json={**payload, **CONTACT}, headers=auth_header(token)
    )
    assert response.status_code == 409


@pytest.mark.parametrize("path", ["/api/admin/bookings", "/api/admin/dashboard", "/api/admin/movies"])
async def test_admin_routes_reject_regular_user(client, path):
    token = await login(client, USER_ID)
    assert (await client.get(path, headers=auth_header(token))).status_code == 403
    assert (await client.get(path)).status_code == 401


async def test_user_cannot_read_someone_elses_booking(client, movie):
    owner = await login(client, USER_ID)
    payload = {"movie_id": movie.id, "show_date": SHOW_DATE, "session": SESSION, "seats": ["1-4"]}
    await client.post("/api/holds", json=payload, headers=auth_header(owner))
    await client.post("/api/bookings/confirm", json={**payload, **CONTACT}, headers=auth_header(owner))
    booking_id = (await client.get("/api/profile/bookings", headers=auth_header(owner))).json()[0]["id"]

    intruder = await login(client, OTHER_ID, "other")
    response = await client.get(f"/api/profile/bookings/{booking_id}", headers=auth_header(intruder))
    assert response.status_code == 404


async def test_review_requires_a_completed_booking(client, movie):
    token = await login(client, USER_ID)
    response = await client.post(
        f"/api/movies/{movie.id}/reviews",
        json={"rating": 5, "text": "Отличный фильм"},
        headers=auth_header(token),
    )
    assert response.status_code == 403
