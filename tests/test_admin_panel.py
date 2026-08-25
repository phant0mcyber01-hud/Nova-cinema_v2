"""Stage 4: endpoints the admin panel relies on."""
from __future__ import annotations

from backend.core.db import SessionLocal
from backend.models import Review
from tests.conftest import (
    ADMIN_ID,
    SESSION,
    SHOW_DATE,
    USER_ID,
    auth_header,
    login,
    watched_booking_in_the_past,
)

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


async def _watched_booking(client, movie_id: int, seats: list[str]) -> tuple[str, str]:
    """A finished, watched screening — the state that unlocks a review."""
    user = await login(client, USER_ID)
    admin = await login(client, ADMIN_ID, "admin")
    await watched_booking_in_the_past(movie_id, 1, ",".join(seats))
    return user, admin


# --- dashboard (4.1) ---------------------------------------------------------


async def test_dashboard_counts_every_lifecycle_status(client, movie):
    user, admin = await _watched_booking(client, movie.id, ["1-1"])
    data = (await client.get("/api/admin/dashboard", headers=auth_header(admin))).json()
    for status in ("pending", "contacting", "confirmed", "cancelled", "watched"):
        assert status in data["statuses"], f"dashboard is missing {status}"
    assert data["statuses"]["watched"] == 1
    assert data["movies"] >= 1
    # No `active_sessions`: it counted the legacy movie-bound schedule, which the
    # booking flow no longer writes to, so the tile would sit at zero forever.
    assert "active_sessions" not in data


async def test_watched_status_stamps_completed_at(client, movie):
    await _watched_booking(client, movie.id, ["1-2"])
    admin = await login(client, ADMIN_ID, "admin")
    row = (await client.get("/api/admin/bookings", headers=auth_header(admin))).json()[0]
    assert row["status"] == "watched"


# --- bookings (4.8) ----------------------------------------------------------


async def test_start_processing_moves_request_to_contacting(client, movie):
    user = await login(client, USER_ID)
    await _book(client, movie.id, ["2-1"], user)
    admin = await login(client, ADMIN_ID, "admin")
    booking_id = (await client.get("/api/admin/bookings", headers=auth_header(admin))).json()[0]["id"]

    response = await client.patch(
        f"/api/admin/bookings/{booking_id}/decision",
        json={"action": "contact", "reason": "", "proposed_session": ""},
        headers=auth_header(admin),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "contacting"

    notifications = (await client.get("/api/profile/notifications", headers=auth_header(user))).json()
    assert any("свяжемся" in item["message"] for item in notifications)


# --- new releases (4.3) ------------------------------------------------------


async def test_admin_marks_and_unmarks_a_new_release(client, movie):
    admin = await login(client, ADMIN_ID, "admin")
    current = (await client.get("/api/admin/movies", headers=auth_header(admin))).json()[0]
    payload = {
        "title": current["title"],
        "genre": current["genre"],
        "description": current["description"],
        "poster": current["poster"],
        "trailer_id": current["trailer_id"],
        "duration": current["duration"],
        "age": current["age"],
        "year": current["year"],
        "country": current["country"],
        "director": current["director"],
        "cast": current["cast"],
        "gallery": current["gallery"],
        "imdb": current["imdb"],
        "kinopoisk": current["kinopoisk"],
        "internal_rating": current["internal_rating"],
        "ticket_price": current["ticket_price"],
        "is_published": True,
        "is_new": True,
        "new_until": "",
        "sort_order": 0,
    }
    assert (
        await client.patch(f"/api/admin/movies/{movie.id}", json=payload, headers=auth_header(admin))
    ).status_code == 200
    assert (await client.get("/api/movies")).json()[0]["is_new"] is True

    payload["is_new"] = False
    await client.patch(f"/api/admin/movies/{movie.id}", json=payload, headers=auth_header(admin))
    assert (await client.get("/api/movies")).json()[0]["is_new"] is False


# --- review moderation -------------------------------------------------------


async def test_admin_hides_and_restores_a_review(client, movie):
    user, admin = await _watched_booking(client, movie.id, ["3-1"])
    posted = await client.post(
        f"/api/movies/{movie.id}/reviews",
        json={"rating": 5, "text": "Отличный фильм"},
        headers=auth_header(user),
    )
    assert posted.status_code == 200

    listed = (await client.get("/api/admin/reviews", headers=auth_header(admin))).json()
    assert len(listed) == 1
    review = listed[0]
    assert review["movie"] == movie.title
    assert review["approved"] is True

    hidden = await client.patch(
        f"/api/admin/reviews/{review['id']}", json={"approved": False}, headers=auth_header(admin)
    )
    assert hidden.status_code == 200
    assert (await client.get(f"/api/movies/{movie.id}")).json()["reviews"] == []

    await client.patch(
        f"/api/admin/reviews/{review['id']}", json={"approved": True}, headers=auth_header(admin)
    )
    assert len((await client.get(f"/api/movies/{movie.id}")).json()["reviews"]) == 1


async def test_admin_deletes_a_review(client, movie):
    user, admin = await _watched_booking(client, movie.id, ["3-2"])
    await client.post(
        f"/api/movies/{movie.id}/reviews",
        json={"rating": 4, "text": "Неплохо"},
        headers=auth_header(user),
    )
    review_id = (await client.get("/api/admin/reviews", headers=auth_header(admin))).json()[0]["id"]

    assert (
        await client.delete(f"/api/admin/reviews/{review_id}", headers=auth_header(admin))
    ).status_code == 200
    assert (await client.get("/api/admin/reviews", headers=auth_header(admin))).json() == []

    async with SessionLocal() as session:
        assert await session.get(Review, review_id) is None


async def test_review_endpoints_reject_regular_users(client):
    token = await login(client, USER_ID)
    assert (await client.get("/api/admin/reviews", headers=auth_header(token))).status_code == 403
    assert (await client.patch("/api/admin/reviews/1", json={"approved": True}, headers=auth_header(token))).status_code == 403


# --- content sections --------------------------------------------------------


async def test_admin_content_endpoints_reject_regular_users(client):
    token = await login(client, USER_ID)
    for path in ("/api/admin/bonuses", "/api/admin/gallery", "/api/admin/settings"):
        assert (await client.get(path, headers=auth_header(token))).status_code == 403
