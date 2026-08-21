"""Stage 9: the booking path end to end, audited against the spec.

Spec: one hall with no seat classes; movie -> date -> session -> seats ->
current price -> request; total = seats x the price the admin set right now.
"""
from __future__ import annotations

from datetime import date, timedelta

from backend.core.db import SessionLocal
from backend.models import Show
from tests.conftest import ADMIN_ID, SESSION, SHOW_DATE, USER_ID, auth_header, login

YESTERDAY = (date.today() - timedelta(days=1)).isoformat()

CONTACT = {
    "first_name": "Иван",
    "last_name": "Петров",
    "phone": "+998 91 326 20 65",
    "telegram_username": "ivanp",
    "comment": "",
}


async def _seats(client, movie_id: int, show_date: str = SHOW_DATE, session_time: str = SESSION):
    return await client.get(
        f"/api/sessions/{movie_id}/seats", params={"show_date": show_date, "session_time": session_time}
    )


async def test_hall_payload_has_no_seat_classes(client, movie):
    """One hall, no VIP/Standard/Premium anywhere in the contract."""
    hall = (await _seats(client, movie.id)).json()
    assert set(hall) == {
        "rows", "cols", "seats_count", "max_seats", "price", "currency",
        "hold_minutes", "booked", "awaiting", "mine", "taken",
    }
    assert hall["seats_count"] == hall["rows"] * hall["cols"]


async def test_full_path_movie_date_session_seats_price_request(client, movie):
    token = await login(client, USER_ID)

    # date -> the sessions offered for it
    sessions = (await client.get(f"/api/movies/{movie.id}/sessions?show_date={SHOW_DATE}")).json()
    assert sessions["sessions"] == [SESSION]

    # session -> the hall and the current price
    hall = (await _seats(client, movie.id)).json()
    price = hall["price"]
    assert price == 30000

    # seats -> quote
    payload = {"movie_id": movie.id, "show_date": SHOW_DATE, "session": SESSION, "seats": ["1-1", "1-2", "2-1"]}
    hold = await client.post("/api/holds", json=payload, headers=auth_header(token))
    assert hold.status_code == 200
    assert hold.json()["total"] == 3 * price

    # request
    confirm = await client.post(
        "/api/bookings/confirm", json={**payload, **CONTACT}, headers=auth_header(token)
    )
    assert confirm.status_code == 200
    body = confirm.json()
    assert body["status"] == "pending"
    assert body["ticket_price"] == price
    assert body["total"] == 3 * price


async def test_total_follows_the_admin_price_at_request_time(client, movie):
    admin = await login(client, ADMIN_ID, "admin")
    await client.patch(
        "/api/admin/settings/base-price", json={"base_ticket_price": 42000}, headers=auth_header(admin)
    )

    assert (await _seats(client, movie.id)).json()["price"] == 42000

    token = await login(client, USER_ID)
    payload = {"movie_id": movie.id, "show_date": SHOW_DATE, "session": SESSION, "seats": ["1-1", "1-2"]}
    await client.post("/api/holds", json=payload, headers=auth_header(token))
    confirm = await client.post(
        "/api/bookings/confirm", json={**payload, **CONTACT}, headers=auth_header(token)
    )
    assert confirm.json()["total"] == 84000


async def test_client_cannot_dictate_the_price(client, movie):
    """A crafted payload must not buy tickets cheaper than the admin set them."""
    token = await login(client, USER_ID)
    payload = {
        "movie_id": movie.id,
        "show_date": SHOW_DATE,
        "session": SESSION,
        "seats": ["1-1"],
        "ticket_price": 1,
        "total": 1,
        **CONTACT,
    }
    await client.post("/api/holds", json=payload, headers=auth_header(token))
    confirm = await client.post("/api/bookings/confirm", json=payload, headers=auth_header(token))
    assert confirm.status_code == 200
    assert confirm.json()["ticket_price"] == 30000
    assert confirm.json()["total"] == 30000


async def test_screening_on_a_past_date_cannot_be_booked(client, movie):
    """The card and the home strip hide past dates; the API must refuse them too."""
    async with SessionLocal() as session:
        session.add(Show(movie_id=movie.id, show_date=YESTERDAY, start_time=SESSION))
        await session.commit()

    assert (await _seats(client, movie.id, YESTERDAY)).status_code == 404

    token = await login(client, USER_ID)
    hold = await client.post(
        "/api/holds",
        json={"movie_id": movie.id, "show_date": YESTERDAY, "session": SESSION, "seats": ["1-1"]},
        headers=auth_header(token),
    )
    assert hold.status_code == 404


async def test_seat_count_is_capped_by_the_admin_setting(client, movie):
    token = await login(client, USER_ID)
    response = await client.post(
        "/api/holds",
        json={
            "movie_id": movie.id,
            "show_date": SHOW_DATE,
            "session": SESSION,
            "seats": ["1-1", "1-2", "1-3", "1-4", "1-5"],
        },
        headers=auth_header(token),
    )
    assert response.status_code == 422


async def test_booking_requires_authentication(client, movie):
    payload = {"movie_id": movie.id, "show_date": SHOW_DATE, "session": SESSION, "seats": ["1-1"]}
    assert (await client.post("/api/holds", json=payload)).status_code == 401
    assert (await client.post("/api/bookings/confirm", json={**payload, **CONTACT})).status_code == 401
