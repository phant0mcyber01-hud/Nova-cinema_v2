"""Reviews are open to anyone signed in, immediately -- no watched booking gate.

The "review after the screening finished" rule (spec 14) made sense when a
booking named a film. It no longer can: a booking is now hall + date + time,
the film is agreed with the administrator afterwards, and `Booking.movie_id`
is NULL for every request created through the generic flow. The gate was
therefore unsatisfiable for anyone, which is the bug the client reported --
"нужно чтоб можно было сразу отзыв фильму ставить" (need to be able to leave
a review right away). Telegram auth already identifies the reviewer, one
review per viewer per movie still holds, and admin moderation (approved) is
still the backstop against anything abusive -- so the gate is simply removed
rather than replaced with an unsatisfiable substitute.

Also: the scale moves from 1-5 to 1-10, per the client's explicit ask.
"""
from __future__ import annotations

from tests.conftest import ADMIN_ID, OTHER_ID, USER_ID, auth_header, login


async def test_any_signed_in_viewer_can_review_without_ever_booking(client, movie):
    """The old gate required a `watched` booking naming this exact film --
    impossible now that a booking never names a film. Signed in is enough."""
    user = await login(client, USER_ID)
    response = await client.post(
        f"/api/movies/{movie.id}/reviews",
        json={"rating": 8, "text": "Отличный фильм"},
        headers=auth_header(user),
    )
    assert response.status_code == 200, response.text

    card = (await client.get(f"/api/movies/{movie.id}")).json()
    assert len(card["reviews"]) == 1
    assert card["reviews"][0]["rating"] == 8


async def test_an_anonymous_visitor_still_cannot_review(client, movie):
    response = await client.post(
        f"/api/movies/{movie.id}/reviews", json={"rating": 9, "text": "Супер"},
    )
    assert response.status_code == 401


async def test_the_card_reports_eligibility_with_no_booking_involved(client, movie):
    anonymous = (await client.get(f"/api/movies/{movie.id}")).json()
    assert anonymous["can_review"] is False
    assert anonymous["has_reviewed"] is False

    user = await login(client, USER_ID)
    signed_in = (await client.get(f"/api/movies/{movie.id}", headers=auth_header(user))).json()
    assert signed_in["can_review"] is True, "signed in is the only requirement now"
    assert signed_in["has_reviewed"] is False

    await client.post(
        f"/api/movies/{movie.id}/reviews", json={"rating": 7, "text": "Хороший фильм"},
        headers=auth_header(user),
    )
    after = (await client.get(f"/api/movies/{movie.id}", headers=auth_header(user))).json()
    assert after["has_reviewed"] is True
    assert after["can_review"] is False, "already reviewed, cannot review again"


# --- one review per viewer per movie, still enforced --------------------------


async def test_one_review_per_viewer_per_movie_still_holds(client, movie):
    user = await login(client, USER_ID)
    first = await client.post(
        f"/api/movies/{movie.id}/reviews", json={"rating": 10, "text": "Великолепно"},
        headers=auth_header(user),
    )
    assert first.status_code == 200

    second = await client.post(
        f"/api/movies/{movie.id}/reviews", json={"rating": 1, "text": "Передумал"},
        headers=auth_header(user),
    )
    assert second.status_code == 409, "one opinion per movie, otherwise the rating is trivial to skew"

    card = (await client.get(f"/api/movies/{movie.id}")).json()
    assert len(card["reviews"]) == 1


async def test_different_viewers_each_get_their_own_review(client, movie):
    first = await login(client, USER_ID)
    second = await login(client, OTHER_ID, "other")

    assert (
        await client.post(
            f"/api/movies/{movie.id}/reviews", json={"rating": 10, "text": "Топ"},
            headers=auth_header(first),
        )
    ).status_code == 200
    assert (
        await client.post(
            f"/api/movies/{movie.id}/reviews", json={"rating": 6, "text": "Неплохо"},
            headers=auth_header(second),
        )
    ).status_code == 200

    card = (await client.get(f"/api/movies/{movie.id}")).json()
    assert len(card["reviews"]) == 2


# --- 1-10 stars, not 1-5 -------------------------------------------------------


async def test_rating_accepts_the_full_one_to_ten_range(client, movie):
    user = await login(client, USER_ID)
    response = await client.post(
        f"/api/movies/{movie.id}/reviews", json={"rating": 10, "text": "Максимум"},
        headers=auth_header(user),
    )
    assert response.status_code == 200, response.text


async def test_rating_above_ten_is_rejected(client, movie):
    user = await login(client, USER_ID)
    response = await client.post(
        f"/api/movies/{movie.id}/reviews", json={"rating": 11, "text": "Слишком много"},
        headers=auth_header(user),
    )
    assert response.status_code == 422


async def test_rating_below_one_is_rejected(client, movie):
    user = await login(client, USER_ID)
    response = await client.post(
        f"/api/movies/{movie.id}/reviews", json={"rating": 0, "text": "Ноль звёзд"},
        headers=auth_header(user),
    )
    assert response.status_code == 422


# --- the average is a plain arithmetic mean of every approved review's stars --


async def test_the_movie_rating_is_the_arithmetic_mean_of_every_review(client, movie):
    first = await login(client, USER_ID)
    second = await login(client, OTHER_ID, "other")

    await client.post(
        f"/api/movies/{movie.id}/reviews", json={"rating": 10, "text": "Отлично"},
        headers=auth_header(first),
    )
    await client.post(
        f"/api/movies/{movie.id}/reviews", json={"rating": 4, "text": "Так себе"},
        headers=auth_header(second),
    )

    card = (await client.get(f"/api/movies/{movie.id}")).json()
    assert card["user_rating"] == 7.0, "(10 + 4) / 2 == 7.0"
    assert card["rating"] == 7.0


async def test_a_hidden_review_does_not_count_toward_the_average(client, movie):
    first = await login(client, USER_ID)
    second = await login(client, OTHER_ID, "other")
    admin = await login(client, ADMIN_ID, "admin")

    await client.post(
        f"/api/movies/{movie.id}/reviews", json={"rating": 10, "text": "Отлично"},
        headers=auth_header(first),
    )
    await client.post(
        f"/api/movies/{movie.id}/reviews", json={"rating": 2, "text": "Не понравилось"},
        headers=auth_header(second),
    )

    reviews = (await client.get("/api/admin/reviews", headers=auth_header(admin))).json()
    low = next(item for item in reviews if item["rating"] == 2)
    await client.patch(
        f"/api/admin/reviews/{low['id']}", json={"approved": False}, headers=auth_header(admin)
    )

    card = (await client.get(f"/api/movies/{movie.id}")).json()
    assert card["user_rating"] == 10.0, "the hidden review is excluded from the mean"
    assert len(card["reviews"]) == 1


async def test_no_reviews_falls_back_to_the_admin_set_internal_rating(client, movie):
    card = (await client.get(f"/api/movies/{movie.id}")).json()
    assert card["reviews"] == []
    assert card["user_rating"] == movie.internal_rating
