"""Stage 14: who may leave a review, and when.

Spec: only a viewer who booked, whose booking was confirmed, whose screening
has finished, and whose booking is `watched`.
"""
from __future__ import annotations

from sqlalchemy import select

from backend.core.db import SessionLocal, utcnow
from backend.models import Booking, Show
from backend.services.booking import session_has_ended
from tests.conftest import (
    ADMIN_ID,
    OTHER_ID,
    SESSION,
    SHOW_DATE,
    USER_ID,
    YESTERDAY,
    auth_header,
    login,
    movie_row,
)

CONTACT = {
    "first_name": "Иван",
    "last_name": "Петров",
    "phone": "+998 91 326 20 65",
    "telegram_username": "ivanp",
    "comment": "",
}

REVIEW = {"rating": 5, "text": "Отличный фильм"}


async def _watched_booking_in_the_past(movie_id: int, user_id: int, seats: str = "1-1") -> int:
    """A booking for yesterday's screening, already marked watched."""
    async with SessionLocal() as session:
        existing = await session.scalar(
            select(Show).where(
                Show.movie_id == movie_id, Show.show_date == YESTERDAY, Show.start_time == "10:00"
            )
        )
        if existing is None:
            session.add(Show(movie_id=movie_id, show_date=YESTERDAY, start_time="10:00", status="active"))
        booking = Booking(
            user_id=user_id,
            movie_id=movie_id,
            show_date=YESTERDAY,
            session="10:00",
            seats=seats,
            status="watched",
            ticket_price=30000,
            total=30000,
            code="x",
            completed_at=utcnow(),
        )
        session.add(booking)
        await session.commit()
        await session.refresh(booking)
        return booking.id


# --- the rule itself ---------------------------------------------------------


def test_session_end_is_start_plus_running_time():
    from datetime import datetime

    # A 120-minute film at 18:00, checked at 19:00 local — still running.
    midway = datetime(2026, 8, 21, 14, 0)  # 19:00 at UTC+5
    assert not session_has_ended("2026-08-21", "18:00", 120, 300, midway)
    # 20:05 local — finished.
    after = datetime(2026, 8, 21, 15, 5)
    assert session_has_ended("2026-08-21", "18:00", 120, 300, after)


def test_session_end_respects_the_cinema_offset():
    from datetime import datetime

    moment = datetime(2026, 8, 21, 16, 0)  # 21:00 at UTC+5, 16:00 at UTC
    assert session_has_ended("2026-08-21", "18:00", 120, 300, moment), "UTC+5: finished at 20:00"
    assert not session_has_ended("2026-08-21", "18:00", 120, 0, moment), "UTC: still an hour to go"


def test_malformed_time_never_counts_as_finished():
    assert not session_has_ended("2026-08-21", "not-a-time", 120, 300)
    assert not session_has_ended("nonsense", "18:00", 120, 300)


# --- the endpoint ------------------------------------------------------------


async def test_a_viewer_who_never_booked_cannot_review(client, movie):
    token = await login(client, USER_ID)
    response = await client.post(
        f"/api/movies/{movie.id}/reviews", json=REVIEW, headers=auth_header(token)
    )
    assert response.status_code == 403


async def test_a_pending_booking_does_not_unlock_the_review(client, movie):
    user = await login(client, USER_ID)
    payload = {"movie_id": movie.id, "show_date": SHOW_DATE, "session": SESSION, "seats": ["1-1"]}
    await client.post("/api/holds", json=payload, headers=auth_header(user))
    await client.post("/api/bookings/confirm", json={**payload, **CONTACT}, headers=auth_header(user))

    response = await client.post(
        f"/api/movies/{movie.id}/reviews", json=REVIEW, headers=auth_header(user)
    )
    assert response.status_code == 403


async def test_watched_but_the_screening_has_not_finished_yet(client, movie):
    """Regression: the admin can mark a booking watched too early by hand."""
    async with SessionLocal() as session:
        session.add(
            Booking(
                user_id=1,
                movie_id=movie.id,
                show_date=SHOW_DATE,  # tomorrow
                session=SESSION,
                seats="1-1",
                status="watched",
                ticket_price=30000,
                total=30000,
                code="x",
            )
        )
        await session.commit()

    user = await login(client, USER_ID)
    response = await client.post(
        f"/api/movies/{movie.id}/reviews", json=REVIEW, headers=auth_header(user)
    )
    assert response.status_code == 403, "the film has not been shown yet"


async def test_watched_and_finished_unlocks_the_review(client, movie):
    user = await login(client, USER_ID)
    await _watched_booking_in_the_past(movie.id, 1)

    response = await client.post(
        f"/api/movies/{movie.id}/reviews", json=REVIEW, headers=auth_header(user)
    )
    assert response.status_code == 200, response.text

    card = (await client.get(f"/api/movies/{movie.id}")).json()
    assert len(card["reviews"]) == 1
    assert card["reviews"][0]["text"] == "Отличный фильм"


async def test_one_review_per_viewer_per_movie(client, movie):
    user = await login(client, USER_ID)
    await _watched_booking_in_the_past(movie.id, 1)

    assert (
        await client.post(f"/api/movies/{movie.id}/reviews", json=REVIEW, headers=auth_header(user))
    ).status_code == 200
    second = await client.post(
        f"/api/movies/{movie.id}/reviews",
        json={"rating": 1, "text": "Передумал"},
        headers=auth_header(user),
    )
    assert second.status_code == 409, "one opinion per movie, otherwise the rating is trivial to skew"

    card = (await client.get(f"/api/movies/{movie.id}")).json()
    assert len(card["reviews"]) == 1


async def test_a_booking_for_another_movie_does_not_unlock_this_one(client, movie):
    async with SessionLocal() as session:
        other = movie_row("Другой фильм")
        session.add(other)
        await session.commit()
        await session.refresh(other)
        other_id = other.id

    await _watched_booking_in_the_past(other_id, 1)
    user = await login(client, USER_ID)
    response = await client.post(
        f"/api/movies/{movie.id}/reviews", json=REVIEW, headers=auth_header(user)
    )
    assert response.status_code == 403


# --- what the card tells the client ------------------------------------------


async def test_card_reports_review_eligibility(client, movie):
    anonymous = (await client.get(f"/api/movies/{movie.id}")).json()
    assert anonymous["can_review"] is False
    assert anonymous["has_reviewed"] is False

    user = await login(client, USER_ID)
    before = (await client.get(f"/api/movies/{movie.id}", headers=auth_header(user))).json()
    assert before["can_review"] is False

    await _watched_booking_in_the_past(movie.id, 1)
    eligible = (await client.get(f"/api/movies/{movie.id}", headers=auth_header(user))).json()
    assert eligible["can_review"] is True
    assert eligible["has_reviewed"] is False

    await client.post(f"/api/movies/{movie.id}/reviews", json=REVIEW, headers=auth_header(user))
    after = (await client.get(f"/api/movies/{movie.id}", headers=auth_header(user))).json()
    assert after["has_reviewed"] is True


async def test_hidden_review_disappears_from_the_card(client, movie):
    user = await login(client, USER_ID)
    await _watched_booking_in_the_past(movie.id, 1)
    await client.post(f"/api/movies/{movie.id}/reviews", json=REVIEW, headers=auth_header(user))

    admin = await login(client, ADMIN_ID, "admin")
    review_id = (await client.get("/api/admin/reviews", headers=auth_header(admin))).json()[0]["id"]
    await client.patch(
        f"/api/admin/reviews/{review_id}", json={"approved": False}, headers=auth_header(admin)
    )

    assert (await client.get(f"/api/movies/{movie.id}")).json()["reviews"] == []


async def test_timezone_offset_is_admin_managed(client):
    admin = await login(client, ADMIN_ID, "admin")
    current = (await client.get("/api/admin/settings", headers=auth_header(admin))).json()
    assert current["timezone_offset_minutes"] == 300, "Uzbekistan is UTC+5"

    current.pop("hall_seats", None)
    current.pop("updated_at", None)
    current["timezone_offset_minutes"] = 0
    saved = await client.put("/api/admin/settings", json=current, headers=auth_header(admin))
    assert saved.status_code == 200
    assert saved.json()["timezone_offset_minutes"] == 0


async def test_reviews_of_other_viewers_are_independent(client, movie):
    first = await login(client, USER_ID)
    second = await login(client, OTHER_ID, "other")
    await _watched_booking_in_the_past(movie.id, 1, "1-1")
    await _watched_booking_in_the_past(movie.id, 2, "1-2")

    assert (
        await client.post(f"/api/movies/{movie.id}/reviews", json=REVIEW, headers=auth_header(first))
    ).status_code == 200
    assert (
        await client.post(
            f"/api/movies/{movie.id}/reviews",
            json={"rating": 4, "text": "Тоже понравилось"},
            headers=auth_header(second),
        )
    ).status_code == 200

    card = (await client.get(f"/api/movies/{movie.id}")).json()
    assert len(card["reviews"]) == 2
    assert card["user_rating"] == 4.5
