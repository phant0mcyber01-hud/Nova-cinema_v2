"""Stage 5: what the Mini App home screen asks of the catalog endpoint."""
from __future__ import annotations

from datetime import date, timedelta

from backend.core.db import SessionLocal
from backend.models import Show
from tests.conftest import SESSION, SHOW_DATE, TODAY, cinema_today, movie_row

OTHER_DATE = (cinema_today() + timedelta(days=2)).isoformat()


async def test_catalog_without_a_date_lists_everything_published(client, movie):
    async with SessionLocal() as session:
        second = movie_row("Второй фильм")
        session.add(second)
        await session.flush()
        session.add(Show(movie_id=second.id, show_date=OTHER_DATE, start_time="12:00"))
        await session.commit()

    titles = [item["title"] for item in (await client.get("/api/movies")).json()]
    assert titles == ["Тестовый фильм", "Второй фильм"]


async def test_date_filter_keeps_only_movies_screening_that_day(client, movie):
    async with SessionLocal() as session:
        second = movie_row("Только послезавтра")
        session.add(second)
        await session.flush()
        session.add(Show(movie_id=second.id, show_date=OTHER_DATE, start_time="12:00"))
        await session.commit()

    today_rows = (await client.get("/api/movies", params={"date": SHOW_DATE})).json()
    assert [item["title"] for item in today_rows] == ["Тестовый фильм"]
    assert today_rows[0]["sessions"] == [SESSION]

    other_rows = (await client.get("/api/movies", params={"date": OTHER_DATE})).json()
    assert [item["title"] for item in other_rows] == ["Только послезавтра"]
    assert other_rows[0]["sessions"] == ["12:00"]


async def test_date_filter_returns_only_that_days_times(client, movie):
    """Without a date the payload merges every day's times; with one it must not."""
    async with SessionLocal() as session:
        session.add(Show(movie_id=movie.id, show_date=OTHER_DATE, start_time="09:15"))
        await session.commit()

    merged = (await client.get("/api/movies")).json()[0]["sessions"]
    assert merged == ["09:15", SESSION]

    narrowed = (await client.get("/api/movies", params={"date": SHOW_DATE})).json()[0]["sessions"]
    assert narrowed == [SESSION]


async def test_inactive_screening_hides_the_movie_from_that_date(client, movie):
    async with SessionLocal() as session:
        hidden = movie_row("Отменённый показ")
        session.add(hidden)
        await session.flush()
        session.add(Show(movie_id=hidden.id, show_date=SHOW_DATE, start_time="20:00", status="cancelled"))
        await session.commit()

    titles = [item["title"] for item in (await client.get("/api/movies", params={"date": SHOW_DATE})).json()]
    assert titles == ["Тестовый фильм"]


async def test_empty_date_returns_an_empty_catalog(client, movie):
    far_future = (cinema_today() + timedelta(days=45)).isoformat()
    assert (await client.get("/api/movies", params={"date": far_future})).json() == []


async def test_malformed_date_is_rejected(client, movie):
    for value in ("2026-8-1", "tomorrow", "01.09.2026"):
        response = await client.get("/api/movies", params={"date": value})
        assert response.status_code == 422, value


async def test_catalog_exposes_the_new_release_flag_for_the_home_strip(client, movie):
    async with SessionLocal() as session:
        fresh = movie_row("Новинка")
        fresh.is_new = True
        session.add(fresh)
        await session.flush()
        session.add(Show(movie_id=fresh.id, show_date=SHOW_DATE, start_time="18:00"))
        await session.commit()

    flags = {item["title"]: item["is_new"] for item in (await client.get("/api/movies")).json()}
    assert flags["Новинка"] is True
    assert flags["Тестовый фильм"] is False


async def test_home_needs_one_settings_call_for_the_date_strip(client):
    """The date strip is driven by booking_dates, not by a constant in the client."""
    settings = (await client.get("/api/settings")).json()
    assert settings["booking_days_ahead"] == len(settings["booking_dates"]) == 8
    assert settings["booking_dates"][0] == TODAY
