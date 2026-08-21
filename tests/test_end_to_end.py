"""Stage 19: the whole journey the spec lists, walked as one story.

    catalog -> movie -> session -> seats -> request -> admin -> confirmation
    -> history -> watched -> review

Everything else is covered piece by piece elsewhere; what was missing was a
single test that proves the pieces still join up.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import select

from backend.core import config
from backend.core.db import SessionLocal
from backend.models import Booking, Movie, Show
from tests.conftest import ADMIN_ID, OTHER_ID, USER_ID, auth_header, login

TODAY = date.today().isoformat()
TOMORROW = (date.today() + timedelta(days=1)).isoformat()
YESTERDAY = (date.today() - timedelta(days=1)).isoformat()

CONTACT = {
    "first_name": "Иван",
    "last_name": "Петров",
    "phone": "+998 91 326 20 65",
    "telegram_username": "ivanp",
    "comment": "Первый ряд, пожалуйста",
}

MOVIE = {
    "title": "Дюна: Часть 2",
    "genre": "Фантастика",
    "description": "Пол Атрейдес защищает Арракис.",
    "poster": "https://example.test/dune.jpg",
    "trailer_id": "Way9Dexny3w",
    "duration": 166,
    "age": 12,
    "year": 2024,
    "country": "США, Канада",
    "director": "Дени Вильнёв",
    "cast": ["Тимоти Шаламе", "Зендея"],
    "gallery": [],
    "imdb": 8.6,
    "kinopoisk": 8.7,
    "internal_rating": None,
    "ticket_price": None,
    "is_published": True,
    "is_new": True,
    "new_until": "",
    "sort_order": 0,
}


@pytest.fixture(autouse=True)
def offline_translation(monkeypatch):
    """Keep the walkthrough off the network: no live translation service."""
    monkeypatch.setattr(config, "TRANSLATION_API_URL", "")


async def _time_passes(booking_id: int) -> None:
    """Move the screening into the past, as the calendar would.

    A viewer books a future session and reviews it afterwards; the test cannot
    wait a day, so the same rows are shifted back instead.
    """
    async with SessionLocal() as session:
        booking = await session.get(Booking, booking_id)
        show = await session.scalar(
            select(Show).where(
                Show.movie_id == booking.movie_id,
                Show.show_date == booking.show_date,
                Show.start_time == booking.session,
            )
        )
        if show is not None:
            show.show_date = YESTERDAY
        booking.show_date = YESTERDAY
        await session.commit()


async def test_the_whole_journey_from_catalog_to_review(client):
    admin = await login(client, ADMIN_ID, "admin")

    # --- the admin prepares the cinema --------------------------------------
    created = await client.post("/api/admin/movies", json=MOVIE, headers=auth_header(admin))
    assert created.status_code == 200, created.text
    movie_id = created.json()["id"]

    schedule = await client.post(
        "/api/admin/sessions/bulk",
        json={
            "movie_id": movie_id,
            "date_from": TODAY,
            "date_to": TOMORROW,
            "times": ["12:00", "19:00"],
            "ticket_price": None,
        },
        headers=auth_header(admin),
    )
    assert schedule.json()["created"] == 4

    priced = await client.patch(
        "/api/admin/settings/base-price",
        json={"base_ticket_price": 40000},
        headers=auth_header(admin),
    )
    assert priced.status_code == 200

    handle = (await client.get("/api/admin/settings", headers=auth_header(admin))).json()
    handle.pop("hall_seats", None)
    handle.pop("updated_at", None)
    handle["bot_username"] = "novacinema_bot"
    assert (await client.put("/api/admin/settings", json=handle, headers=auth_header(admin))).status_code == 200

    # --- the viewer browses the catalogue -----------------------------------
    catalog = (await client.get("/api/movies")).json()
    assert [item["title"] for item in catalog] == ["Дюна: Часть 2"]
    assert catalog[0]["is_new"] is True

    assert [item["title"] for item in (await client.get("/api/movies", params={"q": "вильнёв"})).json()] == [
        "Дюна: Часть 2"
    ], "search reaches the director"
    assert len((await client.get("/api/movies", params={"only_new": "true"})).json()) == 1
    assert (await client.get("/api/movies", params={"date": TODAY})).json()[0]["id"] == movie_id

    # --- the movie card -----------------------------------------------------
    card = (await client.get(f"/api/movies/{movie_id}")).json()
    assert card["director"] == "Дени Вильнёв"
    assert card["cast"] == ["Тимоти Шаламе", "Зендея"]
    assert card["share_link"] == f"https://t.me/novacinema_bot?startapp=movie_{movie_id}"
    assert [day["date"] for day in card["schedule"]] == [TODAY, TOMORROW]
    assert card["schedule"][0]["times"] == ["12:00", "19:00"]
    assert card["can_review"] is False, "nothing has been watched yet"

    # --- date, session, seats, price ----------------------------------------
    user = await login(client, USER_ID)
    sessions = (await client.get(f"/api/movies/{movie_id}/sessions?show_date={TOMORROW}")).json()
    assert sessions["sessions"] == ["12:00", "19:00"]

    hall = (
        await client.get(
            f"/api/sessions/{movie_id}/seats",
            params={"show_date": TOMORROW, "session_time": "19:00"},
        )
    ).json()
    assert (hall["rows"], hall["cols"]) == (3, 5)
    assert hall["price"] == 40000, "the price the admin has just set"
    assert hall["taken"] == []

    booking_payload = {
        "movie_id": movie_id,
        "show_date": TOMORROW,
        "session": "19:00",
        "seats": ["2-2", "2-3"],
    }
    hold = await client.post("/api/holds", json=booking_payload, headers=auth_header(user))
    assert hold.status_code == 200
    assert hold.json()["total"] == 80000

    # --- the request --------------------------------------------------------
    request = await client.post(
        "/api/bookings/confirm", json={**booking_payload, **CONTACT}, headers=auth_header(user)
    )
    assert request.status_code == 200
    assert request.json()["status"] == "pending"
    assert request.json()["total"] == 80000

    seats_now = (
        await client.get(
            f"/api/sessions/{movie_id}/seats",
            params={"show_date": TOMORROW, "session_time": "19:00"},
        )
    ).json()
    assert seats_now["awaiting"] == ["2-2", "2-3"], "awaiting the admin, not yet booked"
    assert seats_now["booked"] == []

    # A price change now must not touch the request already made.
    await client.patch(
        "/api/admin/settings/base-price", json={"base_ticket_price": 55000}, headers=auth_header(admin)
    )

    # --- the administrator handles it ---------------------------------------
    row = (await client.get("/api/admin/bookings", headers=auth_header(admin))).json()[0]
    booking_id = row["id"]
    assert row["name"] == "Иван Петров"
    assert row["phone"] == "+998913262065"
    assert row["chat_url"] == "https://t.me/ivanp"
    assert row["comment"] == "Первый ряд, пожалуйста"
    assert row["seats_count"] == 2
    assert row["ticket_price"] == 40000, "frozen at the price of the moment"

    contacting = await client.patch(
        f"/api/admin/bookings/{booking_id}/decision",
        json={"action": "contact", "reason": "", "proposed_session": ""},
        headers=auth_header(admin),
    )
    assert contacting.json()["status"] == "contacting"

    confirmed = await client.patch(
        f"/api/admin/bookings/{booking_id}/decision",
        json={"action": "confirm", "reason": "", "proposed_session": ""},
        headers=auth_header(admin),
    )
    assert confirmed.json()["status"] == "confirmed"

    after = (
        await client.get(
            f"/api/sessions/{movie_id}/seats",
            params={"show_date": TOMORROW, "session_time": "19:00"},
        )
    ).json()
    assert after["booked"] == ["2-2", "2-3"], "confirmation locks the seats in"

    # --- the viewer's history ------------------------------------------------
    history = (await client.get("/api/profile/bookings", headers=auth_header(user))).json()
    assert len(history) == 1
    ticket = history[0]
    assert ticket["status"] == "confirmed"
    assert ticket["qr_valid"] is True
    assert ticket["seats"] == "2-2,2-3"
    assert ticket["ticket_price"] == 40000, "the later price rise did not rewrite it"
    assert ticket["total"] == 80000

    notifications = (await client.get("/api/profile/notifications", headers=auth_header(user))).json()
    assert any("подтверждена" in item["message"] for item in notifications)

    profile = (await client.get("/api/profile", headers=auth_header(user))).json()
    assert profile["first_name"] == "Иван", "booking details land on the profile"
    assert profile["phone"] == "+998913262065"
    assert profile["bookings"] == 1

    # --- the day comes and goes ---------------------------------------------
    await _time_passes(booking_id)
    watched = await client.patch(
        f"/api/admin/bookings/{booking_id}/status",
        json={"status": "watched"},
        headers=auth_header(admin),
    )
    assert watched.json()["status"] == "watched"

    # --- the review ----------------------------------------------------------
    eligible = (await client.get(f"/api/movies/{movie_id}", headers=auth_header(user))).json()
    assert eligible["can_review"] is True
    assert eligible["has_reviewed"] is False

    review = await client.post(
        f"/api/movies/{movie_id}/reviews",
        json={"rating": 5, "text": "Смотрели всей семьёй, звук отличный"},
        headers=auth_header(user),
    )
    assert review.status_code == 200

    card_now = (await client.get(f"/api/movies/{movie_id}")).json()
    assert len(card_now["reviews"]) == 1
    assert card_now["reviews"][0]["text"] == "Смотрели всей семьёй, звук отличный"
    assert card_now["reviews"][0]["user_name"] == "Зритель", "the author stays anonymous"
    assert card_now["user_rating"] == 5

    # --- the administrator moderates ----------------------------------------
    listed = (await client.get("/api/admin/reviews", headers=auth_header(admin))).json()
    assert listed[0]["user_name"] == "Иван Петров", "the admin does see who wrote it"
    assert listed[0]["telegram_username"] == "tester"
    await client.patch(
        f"/api/admin/reviews/{listed[0]['id']}",
        json={"approved": False},
        headers=auth_header(admin),
    )
    assert (await client.get(f"/api/movies/{movie_id}")).json()["reviews"] == []

    dashboard = (await client.get("/api/admin/dashboard", headers=auth_header(admin))).json()
    assert dashboard["statuses"]["watched"] == 1
    assert dashboard["movies"] == 1
    assert dashboard["potential_income"] == 80000


async def test_the_journey_reads_the_same_in_uzbek(client):
    """Same chain, Uzbek: the viewer must never fall back to Russian."""
    admin = await login(client, ADMIN_ID, "admin")
    created = await client.post("/api/admin/movies", json=MOVIE, headers=auth_header(admin))
    movie_id = created.json()["id"]

    async with SessionLocal() as session:
        movie = await session.get(Movie, movie_id)
        movie.title_uz = "Dyuna: Ikkinchi qism"
        movie.genre_uz = "Fantastika"
        movie.description_uz = "Pol Atreydes Arrakisni himoya qiladi."
        movie.country_uz = "AQSH, Kanada"
        movie.director_uz = "Deni Vilnyov"
        session.add(Show(movie_id=movie_id, show_date=TOMORROW, start_time="19:00"))
        await session.commit()

    catalog = (await client.get("/api/movies", params={"lang": "uz"})).json()
    assert catalog[0]["title"] == "Dyuna: Ikkinchi qism"
    assert catalog[0]["genre"] == "Fantastika"

    found = (await client.get("/api/movies", params={"lang": "uz", "q": "Vilnyov"})).json()
    assert [item["title"] for item in found] == ["Dyuna: Ikkinchi qism"]

    card = (await client.get(f"/api/movies/{movie_id}", params={"lang": "uz"})).json()
    assert card["director"] == "Deni Vilnyov"
    assert card["country"] == "AQSH, Kanada"

    settings = (await client.get("/api/settings", params={"lang": "uz"})).json()
    assert settings["address"] == "Yuksalish 97A"

    user = await login(client, USER_ID)
    payload = {"movie_id": movie_id, "show_date": TOMORROW, "session": "19:00", "seats": ["1-1"]}
    await client.post("/api/holds", json=payload, headers=auth_header(user))
    booked = await client.post(
        "/api/bookings/confirm", json={**payload, **CONTACT}, headers=auth_header(user)
    )
    assert booked.status_code == 200

    history = (await client.get("/api/profile/bookings", params={"lang": "uz"}, headers=auth_header(user))).json()
    assert history[0]["movie"] == "Dyuna: Ikkinchi qism"


async def test_a_cancelled_request_leaves_the_seats_to_the_next_viewer(client, movie):
    """The other branch of the journey: the admin says no."""
    first = await login(client, USER_ID)
    payload = {"movie_id": movie.id, "show_date": TOMORROW, "session": "19:00", "seats": ["1-1"]}
    await client.post("/api/holds", json=payload, headers=auth_header(first))
    await client.post("/api/bookings/confirm", json={**payload, **CONTACT}, headers=auth_header(first))

    admin = await login(client, ADMIN_ID, "admin")
    booking_id = (await client.get("/api/admin/bookings", headers=auth_header(admin))).json()[0]["id"]
    declined = await client.patch(
        f"/api/admin/bookings/{booking_id}/decision",
        json={"action": "decline", "reason": "зал на техобслуживании", "proposed_session": ""},
        headers=auth_header(admin),
    )
    assert declined.json()["status"] == "cancelled"

    notes = (await client.get("/api/profile/notifications", headers=auth_header(first))).json()
    assert any("техобслуживании" in item["message"] for item in notes)

    second = await login(client, OTHER_ID, "other")
    await client.post("/api/holds", json=payload, headers=auth_header(second))
    retaken = await client.post(
        "/api/bookings/confirm", json={**payload, **CONTACT}, headers=auth_header(second)
    )
    assert retaken.status_code == 200, "the freed seat is available again"

    history = (await client.get("/api/profile/bookings", headers=auth_header(first))).json()
    assert history[0]["status"] == "cancelled"
    assert history[0]["qr_valid"] is False
