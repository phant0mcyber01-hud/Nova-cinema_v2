"""Stage 6: what the movie card needs — grouped schedule and the share handle."""
from __future__ import annotations

from datetime import date, timedelta

from backend.core.db import SessionLocal
from backend.models import Show
from tests.conftest import ADMIN_ID, SESSION, SHOW_DATE, auth_header, login

YESTERDAY = (date.today() - timedelta(days=1)).isoformat()
TODAY = date.today().isoformat()
FAR_AHEAD = (date.today() + timedelta(days=40)).isoformat()


async def test_card_groups_screenings_by_date(client, movie):
    async with SessionLocal() as session:
        session.add_all([
            Show(movie_id=movie.id, show_date=TODAY, start_time="21:00"),
            Show(movie_id=movie.id, show_date=TODAY, start_time="10:30"),
            Show(movie_id=movie.id, show_date=SHOW_DATE, start_time="12:00"),
        ])
        await session.commit()

    schedule = (await client.get(f"/api/movies/{movie.id}")).json()["schedule"]
    assert schedule == [
        {"date": TODAY, "times": ["10:30", "21:00"]},
        {"date": SHOW_DATE, "times": ["12:00", SESSION]},
    ]


async def test_card_hides_past_and_out_of_window_screenings(client, movie):
    async with SessionLocal() as session:
        session.add_all([
            Show(movie_id=movie.id, show_date=YESTERDAY, start_time="18:00"),
            Show(movie_id=movie.id, show_date=FAR_AHEAD, start_time="18:00"),
        ])
        await session.commit()

    dates = [day["date"] for day in (await client.get(f"/api/movies/{movie.id}")).json()["schedule"]]
    assert YESTERDAY not in dates, "a screening that already happened must not be offered"
    assert FAR_AHEAD not in dates, "the card must respect booking_days_ahead"
    assert dates == [SHOW_DATE]


async def test_card_hides_inactive_screenings(client, movie):
    async with SessionLocal() as session:
        session.add(Show(movie_id=movie.id, show_date=SHOW_DATE, start_time="23:00", status="cancelled"))
        await session.commit()

    schedule = (await client.get(f"/api/movies/{movie.id}")).json()["schedule"]
    assert schedule == [{"date": SHOW_DATE, "times": [SESSION]}]


async def test_card_without_screenings_returns_an_empty_schedule(client):
    async with SessionLocal() as session:
        from tests.conftest import movie_row

        lonely = movie_row("Без сеансов")
        session.add(lonely)
        await session.commit()
        await session.refresh(lonely)
        movie_id = lonely.id

    assert (await client.get(f"/api/movies/{movie_id}")).json()["schedule"] == []


async def test_schedule_window_follows_the_admin_setting(client, movie):
    """Shrinking booking_days_ahead must shrink the card, not just the home strip."""
    async with SessionLocal() as session:
        session.add(Show(movie_id=movie.id, show_date=SHOW_DATE, start_time="12:00"))
        await session.commit()

    admin = await login(client, ADMIN_ID, "admin")
    current = (await client.get("/api/admin/settings", headers=auth_header(admin))).json()
    current.pop("hall_seats", None)
    current.pop("updated_at", None)
    current["booking_days_ahead"] = 1  # today only
    assert (await client.put("/api/admin/settings", json=current, headers=auth_header(admin))).status_code == 200

    assert (await client.get(f"/api/movies/{movie.id}")).json()["schedule"] == []


async def test_bot_username_is_exposed_for_the_share_link(client):
    assert (await client.get("/api/settings")).json()["bot_username"] == ""

    admin = await login(client, ADMIN_ID, "admin")
    current = (await client.get("/api/admin/settings", headers=auth_header(admin))).json()
    current.pop("hall_seats", None)
    current.pop("updated_at", None)
    current["bot_username"] = "@novacinema_bot"
    assert (await client.put("/api/admin/settings", json=current, headers=auth_header(admin))).status_code == 200

    # The public payload strips the @ so the client can build t.me/<bot>?startapp=…
    assert (await client.get("/api/settings")).json()["bot_username"] == "novacinema_bot"


async def test_bot_username_rejects_a_malformed_handle(client):
    admin = await login(client, ADMIN_ID, "admin")
    current = (await client.get("/api/admin/settings", headers=auth_header(admin))).json()
    current.pop("hall_seats", None)
    current.pop("updated_at", None)
    current["bot_username"] = "not a handle!"
    response = await client.put("/api/admin/settings", json=current, headers=auth_header(admin))
    assert response.status_code == 422


async def test_card_still_carries_everything_the_spec_lists(client, movie):
    data = (await client.get(f"/api/movies/{movie.id}")).json()
    for field in (
        "poster", "title", "genre", "description", "duration", "age",
        "rating", "reviews", "trailer_id", "schedule", "ticket_price", "is_new",
    ):
        assert field in data, f"movie card is missing {field}"


async def test_cast_falls_back_to_the_base_column(client):
    """Regression: `cast_json_ru or cast_json` picked the truthy default "[]"."""
    import json

    from tests.conftest import movie_row

    async with SessionLocal() as session:
        item = movie_row("С актёрами")
        item.cast_json = json.dumps(["Тимоти Шаламе", "Зендея"])
        # cast_json_ru / cast_json_uz keep their "[]" defaults, as after a seed.
        session.add(item)
        await session.commit()
        await session.refresh(item)
        movie_id = item.id

    assert (await client.get(f"/api/movies/{movie_id}")).json()["cast"] == ["Тимоти Шаламе", "Зендея"]
    uz = await client.get(f"/api/movies/{movie_id}", params={"lang": "uz"})
    assert uz.json()["cast"] == ["Тимоти Шаламе", "Зендея"]
