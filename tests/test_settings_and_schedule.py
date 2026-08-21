"""Stage 3: everything is admin-managed — settings, price, schedule, content."""
from __future__ import annotations

from datetime import date, timedelta

from backend.core.db import SessionLocal
from tests.conftest import ADMIN_ID, SESSION, SHOW_DATE, USER_ID, auth_header, login, movie_row

CONTACT = {
    "first_name": "Иван",
    "last_name": "Петров",
    "phone": "+998 91 326 20 65",
    "telegram_username": "ivanp",
    "comment": "",
}


async def _book(client, movie_id: int, seats: list[str], token: str) -> dict:
    payload = {"movie_id": movie_id, "show_date": SHOW_DATE, "session": SESSION, "seats": seats}
    await client.post("/api/holds", json=payload, headers=auth_header(token))
    response = await client.post(
        "/api/bookings/confirm", json={**payload, **CONTACT}, headers=auth_header(token)
    )
    assert response.status_code == 200, response.text
    return response.json()


# --- settings ----------------------------------------------------------------


async def test_public_settings_expose_the_seeded_cinema_profile(client):
    response = await client.get("/api/settings")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Nova Cinema"
    assert data["address"] == "Юксалиш 97А"
    assert data["phone"] == "+998 91 326 20 65"
    assert data["telegram_url"] == "https://t.me/novasinema"
    assert (data["hall_rows"], data["hall_cols"], data["hall_seats"]) == (3, 5, 15)
    assert data["currency"] == "UZS"
    assert len(data["booking_dates"]) == 7


async def test_public_settings_localise_to_uzbek(client):
    response = await client.get("/api/settings", params={"lang": "uz"})
    assert response.json()["address"] == "Yuksalish 97A"


async def test_admin_edits_contacts_without_touching_code(client):
    token = await login(client, ADMIN_ID, "admin")
    current = (await client.get("/api/admin/settings", headers=auth_header(token))).json()
    current.pop("hall_seats", None)
    current.pop("updated_at", None)
    current.update({"name": "Nova Cinema Fergana", "phone": "+998 90 000 00 00", "address": "Новый адрес 1"})

    saved = await client.put("/api/admin/settings", json=current, headers=auth_header(token))
    assert saved.status_code == 200, saved.text

    public = (await client.get("/api/settings")).json()
    assert public["name"] == "Nova Cinema Fergana"
    assert public["phone"] == "+998 90 000 00 00"
    assert public["address"] == "Новый адрес 1"


async def test_admin_resizes_the_hall(client, movie):
    token = await login(client, ADMIN_ID, "admin")
    current = (await client.get("/api/admin/settings", headers=auth_header(token))).json()
    current.pop("hall_seats", None)
    current.pop("updated_at", None)
    current.update({"hall_rows": 4, "hall_cols": 6, "max_seats_per_booking": 6})
    assert (await client.put("/api/admin/settings", json=current, headers=auth_header(token))).status_code == 200

    hall = (
        await client.get(
            f"/api/sessions/{movie.id}/seats", params={"show_date": SHOW_DATE, "session_time": SESSION}
        )
    ).json()
    assert (hall["rows"], hall["cols"], hall["seats_count"]) == (4, 6, 24)
    assert hall["max_seats"] == 6

    # A seat that only exists in the enlarged hall is now bookable.
    user = await login(client, USER_ID)
    response = await client.post(
        "/api/holds",
        json={"movie_id": movie.id, "show_date": SHOW_DATE, "session": SESSION, "seats": ["4-6"]},
        headers=auth_header(user),
    )
    assert response.status_code == 200


# --- price -------------------------------------------------------------------


async def test_price_change_applies_forward_and_freezes_existing_bookings(client, movie):
    """Spec 4.5: new bookings use the new price, old ones keep their own."""
    user = await login(client, USER_ID)
    first = await _book(client, movie.id, ["1-1"], user)
    assert first["ticket_price"] == 30000
    assert first["total"] == 30000

    admin = await login(client, ADMIN_ID, "admin")
    changed = await client.patch(
        "/api/admin/settings/base-price", json={"base_ticket_price": 35000}, headers=auth_header(admin)
    )
    assert changed.status_code == 200

    hall = (
        await client.get(
            f"/api/sessions/{movie.id}/seats", params={"show_date": SHOW_DATE, "session_time": SESSION}
        )
    ).json()
    assert hall["price"] == 35000

    second = await _book(client, movie.id, ["2-1"], user)
    assert second["ticket_price"] == 35000

    history = (await client.get("/api/profile/bookings", headers=auth_header(user))).json()
    by_seat = {item["seats"]: item for item in history}
    assert by_seat["1-1"]["ticket_price"] == 30000, "an existing booking must keep its historical price"
    assert by_seat["1-1"]["total"] == 30000
    assert by_seat["2-1"]["ticket_price"] == 35000


# --- schedule ----------------------------------------------------------------


async def test_only_scheduled_times_are_bookable(client, movie):
    """The old code accepted any well-formed HH:MM; the schedule is real now."""
    user = await login(client, USER_ID)
    response = await client.post(
        "/api/holds",
        json={"movie_id": movie.id, "show_date": SHOW_DATE, "session": "03:45", "seats": ["1-1"]},
        headers=auth_header(user),
    )
    assert response.status_code == 404

    seats = await client.get(
        f"/api/sessions/{movie.id}/seats", params={"show_date": SHOW_DATE, "session_time": "03:45"}
    )
    assert seats.status_code == 404


async def test_admin_creates_a_screening_that_becomes_bookable(client, movie):
    admin = await login(client, ADMIN_ID, "admin")
    created = await client.post(
        "/api/admin/sessions",
        json={"movie_id": movie.id, "show_date": SHOW_DATE, "start_time": "21:30", "status": "active"},
        headers=auth_header(admin),
    )
    assert created.status_code == 200, created.text

    listed = (await client.get(f"/api/movies/{movie.id}/sessions?show_date={SHOW_DATE}")).json()
    assert listed["sessions"] == ["19:00", "21:30"]

    user = await login(client, USER_ID)
    response = await client.post(
        "/api/holds",
        json={"movie_id": movie.id, "show_date": SHOW_DATE, "session": "21:30", "seats": ["1-1"]},
        headers=auth_header(user),
    )
    assert response.status_code == 200


async def test_bulk_schedule_fills_a_date_range(client, movie):
    admin = await login(client, ADMIN_ID, "admin")
    start = date.today().isoformat()
    end = (date.today() + timedelta(days=2)).isoformat()
    response = await client.post(
        "/api/admin/sessions/bulk",
        json={"movie_id": movie.id, "date_from": start, "date_to": end, "times": ["10:00", "14:00"]},
        headers=auth_header(admin),
    )
    assert response.status_code == 200
    assert response.json()["created"] == 6

    listed = (await client.get(f"/api/movies/{movie.id}/sessions?show_date={start}")).json()
    assert listed["sessions"] == ["10:00", "14:00"]


async def test_screening_with_bookings_cannot_be_deleted(client, movie):
    user = await login(client, USER_ID)
    await _book(client, movie.id, ["1-1"], user)

    admin = await login(client, ADMIN_ID, "admin")
    shows = (await client.get("/api/admin/sessions", headers=auth_header(admin))).json()
    show_id = shows[0]["id"]
    response = await client.delete(f"/api/admin/sessions/{show_id}", headers=auth_header(admin))
    assert response.status_code == 409


# --- booking lifecycle -------------------------------------------------------


async def test_cancelling_frees_the_seat_and_confirming_keeps_it(client, movie):
    user = await login(client, USER_ID)
    await _book(client, movie.id, ["1-3"], user)
    admin = await login(client, ADMIN_ID, "admin")
    booking_id = (await client.get("/api/admin/bookings", headers=auth_header(admin))).json()[0]["id"]

    taken = lambda payload: payload["taken"]  # noqa: E731
    seats_url = f"/api/sessions/{movie.id}/seats"
    params = {"show_date": SHOW_DATE, "session_time": SESSION}
    assert taken((await client.get(seats_url, params=params)).json()) == ["1-3"]

    await client.patch(
        f"/api/admin/bookings/{booking_id}/decision",
        json={"action": "decline", "reason": "нет мест", "proposed_session": ""},
        headers=auth_header(admin),
    )
    assert taken((await client.get(seats_url, params=params)).json()) == []


async def test_contacting_status_keeps_the_seat(client, movie):
    user = await login(client, USER_ID)
    await _book(client, movie.id, ["2-2"], user)
    admin = await login(client, ADMIN_ID, "admin")
    booking_id = (await client.get("/api/admin/bookings", headers=auth_header(admin))).json()[0]["id"]

    response = await client.patch(
        f"/api/admin/bookings/{booking_id}/decision",
        json={"action": "contact", "reason": "", "proposed_session": ""},
        headers=auth_header(admin),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "contacting"

    seats = await client.get(
        f"/api/sessions/{movie.id}/seats", params={"show_date": SHOW_DATE, "session_time": SESSION}
    )
    assert seats.json()["taken"] == ["2-2"]


async def test_watched_status_unlocks_the_review(client, movie):
    user = await login(client, USER_ID)
    await _book(client, movie.id, ["3-1"], user)
    admin = await login(client, ADMIN_ID, "admin")
    booking_id = (await client.get("/api/admin/bookings", headers=auth_header(admin))).json()[0]["id"]

    blocked = await client.post(
        f"/api/movies/{movie.id}/reviews",
        json={"rating": 5, "text": "Отличный фильм"},
        headers=auth_header(user),
    )
    assert blocked.status_code == 403

    await client.patch(
        f"/api/admin/bookings/{booking_id}/status",
        json={"status": "watched"},
        headers=auth_header(admin),
    )
    allowed = await client.post(
        f"/api/movies/{movie.id}/reviews",
        json={"rating": 5, "text": "Отличный фильм"},
        headers=auth_header(user),
    )
    assert allowed.status_code == 200


async def test_admin_booking_row_carries_everything_the_spec_asks_for(client, movie):
    user = await login(client, USER_ID)
    await _book(client, movie.id, ["1-1", "1-2"], user)
    admin = await login(client, ADMIN_ID, "admin")
    row = (await client.get("/api/admin/bookings", headers=auth_header(admin))).json()[0]
    for field in (
        "movie", "show_date", "session", "seats", "seats_count", "total", "ticket_price",
        "name", "telegram_username", "telegram_id", "created_at", "status",
    ):
        assert row[field] is not None, f"missing {field}"
    assert row["seats_count"] == 2
    assert row["telegram_id"] == USER_ID


# --- new releases ------------------------------------------------------------


async def test_new_release_flag_expires(client):
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    async with SessionLocal() as session:
        active = movie_row("Новинка активная")
        active.is_new, active.new_until = True, tomorrow
        expired = movie_row("Новинка истёкшая")
        expired.is_new, expired.new_until = True, yesterday
        forever = movie_row("Новинка бессрочная")
        forever.is_new = True
        session.add_all([active, expired, forever])
        await session.commit()

    catalog = {item["title"]: item["is_new"] for item in (await client.get("/api/movies")).json()}
    assert catalog["Новинка активная"] is True
    assert catalog["Новинка бессрочная"] is True
    assert catalog["Новинка истёкшая"] is False


# --- content -----------------------------------------------------------------


async def test_bonuses_are_managed_by_the_admin(client):
    admin = await login(client, ADMIN_ID, "admin")
    created = await client.post(
        "/api/admin/bonuses",
        json={"title": "Скидка 10%", "title_uz": "10% chegirma", "text": "По промокоду NOVA10", "is_active": True},
        headers=auth_header(admin),
    )
    assert created.status_code == 200

    public = (await client.get("/api/bonuses")).json()
    assert public[0]["title"] == "Скидка 10%"
    assert (await client.get("/api/bonuses", params={"lang": "uz"})).json()[0]["title"] == "10% chegirma"

    bonus_id = created.json()["id"]
    await client.patch(
        f"/api/admin/bonuses/{bonus_id}",
        json={"title": "Скидка 10%", "text": "", "is_active": False},
        headers=auth_header(admin),
    )
    assert (await client.get("/api/bonuses")).json() == []


async def test_melodies_are_capped_at_three(client):
    admin = await login(client, ADMIN_ID, "admin")
    for index in range(3):
        response = await client.post(
            "/api/admin/melodies",
            json={"title": f"Мелодия {index + 1}", "file_url": f"/uploads/m{index}.mp3"},
            headers=auth_header(admin),
        )
        assert response.status_code == 200

    overflow = await client.post(
        "/api/admin/melodies",
        json={"title": "Четвёртая", "file_url": "/uploads/m4.mp3"},
        headers=auth_header(admin),
    )
    assert overflow.status_code == 409
    assert len((await client.get("/api/melodies")).json()) == 3


async def test_gallery_images_are_managed_by_the_admin(client):
    admin = await login(client, ADMIN_ID, "admin")
    created = await client.post(
        "/api/admin/gallery",
        json={"image_url": "/uploads/hall.jpg", "caption": "Зал", "caption_uz": "Zal"},
        headers=auth_header(admin),
    )
    assert created.status_code == 200
    assert (await client.get("/api/gallery")).json()[0]["caption"] == "Зал"
    assert (await client.get("/api/gallery", params={"lang": "uz"})).json()[0]["caption"] == "Zal"


async def test_legacy_session_field_is_still_accepted(client, movie):
    """The stage-2 admin form posts `session`; stage 4 will switch to `start_time`."""
    admin = await login(client, ADMIN_ID, "admin")
    response = await client.post(
        "/api/admin/sessions",
        json={
            "movie_id": movie.id,
            "show_date": SHOW_DATE,
            "session": "16:45",
            "seats_count": 80,
            "status": "active",
        },
        headers=auth_header(admin),
    )
    assert response.status_code == 200, response.text
    listed = (await client.get(f"/api/movies/{movie.id}/sessions?show_date={SHOW_DATE}")).json()
    assert "16:45" in listed["sessions"]


async def test_sessions_endpoint_returns_empty_list_for_a_date_without_shows(client, movie):
    """Contract behind the Mini App's "no screenings on this date" state."""
    empty_day = (date.today() + timedelta(days=30)).isoformat()
    response = await client.get(f"/api/movies/{movie.id}/sessions?show_date={empty_day}")
    assert response.status_code == 200
    assert response.json()["sessions"] == []
