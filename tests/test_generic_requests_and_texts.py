"""Phase A: how a filmless request reads everywhere it is shown.

A generic booking has `movie_id` NULL, so every screen that used to join the
movies table has to survive that -- the profile, the admin list, the QR ticket
and the Telegram messages.  What none of them may do is invent a film the
viewer was never promised.
"""
from __future__ import annotations

from sqlalchemy import select

from backend.core.db import SessionLocal
from backend.models import Booking
from tests.conftest import ADMIN_ID, SESSION, SHOW_DATE, USER_ID, auth_header, login
from tests.test_generic_booking import CONTACT, SLOT, book, hold

ADMIN_PHONE = "91 326 20 65"
ADMIN_TELEGRAM = "@Hhkcjoj"


async def _decide(client, admin: str, booking_id: int, action: str, **extra):
    return await client.patch(
        f"/api/admin/bookings/{booking_id}/decision",
        json={"action": action, "reason": "", "proposed_session": "", **extra},
        headers=auth_header(admin),
    )


# --- the viewer's own history ------------------------------------------------


async def test_the_profile_shows_a_filmless_request_without_breaking(client):
    token = await login(client, USER_ID)
    await book(client, token, 3)

    history = await client.get("/api/profile/bookings", headers=auth_header(token))
    assert history.status_code == 200, history.text
    entry = history.json()[0]
    assert entry["movie_id"] is None
    assert entry["movie"] == "Nova Cinema"
    assert entry["movie_agreed"] is False
    assert entry["party_size"] == 3
    assert entry["seats_count"] == 3
    assert entry["total"] == 90000
    assert entry["show_date"] == SHOW_DATE
    assert entry["session"] == SLOT


async def test_the_internal_capacity_tokens_are_never_shown_as_seats(client):
    token = await login(client, USER_ID)
    await book(client, token, 2)
    entry = (await client.get("/api/profile/bookings", headers=auth_header(token))).json()[0]
    assert entry["seats"] == "", "no row and no chair was ever reserved"


async def test_a_single_filmless_request_can_be_opened(client):
    token = await login(client, USER_ID)
    created = await book(client, token, 2)
    detail = await client.get(
        f"/api/profile/bookings/{created['id']}", headers=auth_header(token)
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["movie"] == "Nova Cinema"


async def test_the_qr_ticket_survives_a_request_with_no_film(client):
    user = await login(client, USER_ID)
    created = await book(client, user, 2)
    admin = await login(client, ADMIN_ID, "admin")
    assert (await _decide(client, admin, created["id"], "confirm")).status_code == 200

    entry = (await client.get("/api/profile/bookings", headers=auth_header(user))).json()[0]
    assert entry["qr_valid"] is True
    assert entry["qr_token"]
    assert entry["uuid"]


async def test_a_movie_bound_booking_still_reads_as_before(client, movie):
    """The legacy history must not be flattened into "Nova Cinema"."""
    token = await login(client, USER_ID)
    payload = {"movie_id": movie.id, "show_date": SHOW_DATE, "session": SESSION, "seats": ["1-1"]}
    await client.post("/api/holds", json=payload, headers=auth_header(token))
    assert (
        await client.post(
            "/api/bookings/confirm", json={**payload, **CONTACT}, headers=auth_header(token)
        )
    ).status_code == 200

    entry = (await client.get("/api/profile/bookings", headers=auth_header(token))).json()[0]
    assert entry["movie"] == movie.title
    assert entry["movie_agreed"] is True
    assert entry["seats"] == "1-1"


# --- the admin list ----------------------------------------------------------


async def test_the_admin_list_shows_a_request_that_has_no_film(client):
    user = await login(client, USER_ID)
    await book(client, user, 5)
    admin = await login(client, ADMIN_ID, "admin")

    rows = await client.get("/api/admin/bookings", headers=auth_header(admin))
    assert rows.status_code == 200, rows.text
    row = rows.json()[0]
    assert row["movie_id"] is None
    assert row["movie"] == "Nova Cinema"
    assert row["party_size"] == 5
    assert row["seats_count"] == 5
    assert row["total"] == 150000
    assert row["telegram_username"] == "ivanp"


async def test_the_status_history_still_round_trips(client):
    user = await login(client, USER_ID)
    created = await book(client, user, 2)
    admin = await login(client, ADMIN_ID, "admin")

    assert (await _decide(client, admin, created["id"], "contact")).status_code == 200
    proposed = await _decide(client, admin, created["id"], "propose", proposed_session="20:00")
    assert proposed.status_code == 200
    row = (await client.get("/api/admin/bookings", headers=auth_header(admin))).json()[0]
    assert row["status"] == "contacting"
    assert row["proposed_session"] == "20:00"

    declined = await _decide(client, admin, created["id"], "decline", reason="зал на ремонте")
    assert declined.json()["admin_note"] == "зал на ремонте"


# --- reviews -----------------------------------------------------------------


async def test_a_signed_in_viewer_can_review_without_any_booking_at_all(client, movie):
    """The old movie-bound gate is gone: signed in is the whole requirement,
    exactly because a generic request never names a film to begin with."""
    user = await login(client, USER_ID)

    card = await client.get(f"/api/movies/{movie.id}", headers=auth_header(user))
    assert card.json()["can_review"] is True
    posted = await client.post(
        f"/api/movies/{movie.id}/reviews",
        json={"rating": 9, "text": "Отлично"},
        headers=auth_header(user),
    )
    assert posted.status_code == 200


async def test_a_generic_request_marked_watched_does_not_change_review_eligibility(client, movie):
    """Marking a hall request `watched` has no film attached to unlock -- it
    simply has no effect on review eligibility either way."""
    user = await login(client, USER_ID)
    created = await book(client, user, 2)
    admin = await login(client, ADMIN_ID, "admin")
    await client.patch(
        f"/api/admin/bookings/{created['id']}/status",
        json={"status": "watched"},
        headers=auth_header(admin),
    )

    card = await client.get(f"/api/movies/{movie.id}", headers=auth_header(user))
    assert card.json()["can_review"] is True


# --- what the administrator is sent ------------------------------------------


async def test_the_admin_message_carries_the_request_and_no_film(client, telegram_outbox):
    token = await login(client, USER_ID)
    assert (await hold(client, token, 3)).status_code == 200
    response = await client.post(
        "/api/booking/requests",
        json={
            "date": SHOW_DATE,
            "time": SLOT,
            "party_size": 3,
            **CONTACT,
            "comment": "Днём рождения",
            "promo_code": "NOVA10",
        },
        headers=auth_header(token),
    )
    assert response.status_code == 200, response.text

    text = next(item for item in telegram_outbox.texts() if "заявка" in item.lower())
    assert "Фильм" not in text, "the mini app does not book a film"
    assert "Гостей: 3" in text
    assert "18:00" in text
    assert "Сумма: 90" in text
    assert "+998913262065" in text
    assert "@ivanp" in text
    assert "NOVA10" in text
    assert "Днём рождения" in text
    assert telegram_outbox.chat_ids() == [ADMIN_ID]


async def test_the_acknowledgement_promises_no_seat_and_no_film(client):
    token = await login(client, USER_ID)
    assert (await hold(client, token, 3)).status_code == 200
    body = (
        await client.post(
            "/api/booking/requests",
            json={"date": SHOW_DATE, "time": SLOT, "party_size": 3, **CONTACT},
            headers=auth_header(token),
        )
    ).json()
    message = body["message"]
    assert "без выбора конкретного ряда и кресла" in message
    assert "не закрепляется автоматически" in message
    assert "Гостей: 3" in message


async def test_the_confirmation_is_honest_and_carries_both_contacts(client, telegram_outbox):
    user = await login(client, USER_ID)
    created = await book(client, user, 3)
    admin = await login(client, ADMIN_ID, "admin")
    telegram_outbox.clear()
    assert (await _decide(client, admin, created["id"], "confirm")).status_code == 200

    text = telegram_outbox.texts()[-1]
    assert f"Бронирование №{created['id']} подтверждено" in text
    assert "Гостей: 3" in text
    assert "без выбора конкретного ряда и кресла" in text
    assert "согласуйте детали и оплату с администратором" in text
    assert ADMIN_PHONE in text
    assert ADMIN_TELEGRAM in text

    notes = (await client.get("/api/profile/notifications", headers=auth_header(user))).json()
    assert any("подтверждено" in item["message"] for item in notes)


async def test_a_movie_bound_confirmation_still_names_the_film(client, movie):
    """Only a filmless request gets the generic text."""
    token = await login(client, USER_ID)
    payload = {"movie_id": movie.id, "show_date": SHOW_DATE, "session": SESSION, "seats": ["1-1"]}
    await client.post("/api/holds", json=payload, headers=auth_header(token))
    await client.post(
        "/api/bookings/confirm", json={**payload, **CONTACT}, headers=auth_header(token)
    )
    admin = await login(client, ADMIN_ID, "admin")
    async with SessionLocal() as session:
        booking_id = (await session.scalar(select(Booking))).id
    confirmed = await _decide(client, admin, booking_id, "confirm")
    assert confirmed.status_code == 200

    notes = (await client.get("/api/profile/notifications", headers=auth_header(token))).json()
    assert any(movie.title in item["message"] for item in notes)


async def test_the_dates_are_written_the_way_a_person_reads_them():
    from backend.services.telegram import format_date, format_money

    assert format_date("2026-08-27") == "27 августа"
    assert format_date("2026-01-03") == "3 января"
    assert format_date("не дата") == "не дата"
    assert format_money(90000, "UZS").replace(" ", " ") == "90 000 сум"


# --- the administrator's own contacts are admin-managed ----------------------


async def test_the_admin_contacts_are_seeded_and_editable(client):
    admin = await login(client, ADMIN_ID, "admin")
    current = (await client.get("/api/admin/settings", headers=auth_header(admin))).json()
    assert current["admin_phone"] == ADMIN_PHONE
    assert current["admin_telegram"] == ADMIN_TELEGRAM

    current.pop("hall_seats", None)
    current.pop("updated_at", None)
    current["admin_telegram"] = "@NovaAdmin"
    saved = await client.put("/api/admin/settings", json=current, headers=auth_header(admin))
    assert saved.status_code == 200, saved.text
    assert saved.json()["admin_telegram"] == "@NovaAdmin"

    public = (await client.get("/api/settings")).json()
    assert public["admin_phone"] == ADMIN_PHONE
    assert public["admin_telegram"] == "@NovaAdmin"
