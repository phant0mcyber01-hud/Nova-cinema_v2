"""Stage 14 historical note: reviews used to gate on a watched booking naming
the exact film. That rule is gone (see test_reviews_open_and_ten_scale.py) --
a booking no longer names a film at all, so the gate became unsatisfiable for
every viewer. What remains here: `session_has_ended` as a standalone time
utility (still exported, no longer wired to review eligibility), review
moderation, and the settings knob it happens to share a file with.
"""
from __future__ import annotations

from backend.services.booking import session_has_ended
from tests.conftest import ADMIN_ID, OTHER_ID, USER_ID, auth_header, login

REVIEW = {"rating": 8, "text": "Отличный фильм"}


# --- session_has_ended as a plain time calculation -----------------------------


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


# --- moderation ----------------------------------------------------------------


async def test_hidden_review_disappears_from_the_card(client, movie):
    user = await login(client, USER_ID)
    await client.post(f"/api/movies/{movie.id}/reviews", json=REVIEW, headers=auth_header(user))

    admin = await login(client, ADMIN_ID, "admin")
    review_id = (await client.get("/api/admin/reviews", headers=auth_header(admin))).json()[0]["id"]
    await client.patch(
        f"/api/admin/reviews/{review_id}", json={"approved": False}, headers=auth_header(admin)
    )

    assert (await client.get(f"/api/movies/{movie.id}")).json()["reviews"] == []


# --- an unrelated setting that historically lived in this file -----------------


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
    assert card["user_rating"] == 6.0, "(8 + 4) / 2 == 6.0"
