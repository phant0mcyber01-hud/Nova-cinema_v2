"""Stage 7: search across the catalog and the new-release filter."""
from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

from backend.core.db import SessionLocal
from backend.models import Show
from tests.conftest import SHOW_DATE, movie_row


async def _catalog(client, **params) -> list[str]:
    response = await client.get("/api/movies", params=params)
    assert response.status_code == 200, response.text
    return [item["title"] for item in response.json()]


@pytest.fixture
async def library(movie):
    """A small catalog with distinct values in every searchable field."""
    async with SessionLocal() as session:
        dune = movie_row("Дюна: Часть 2")
        dune.genre = "Фантастика"
        dune.country = "США, Канада"
        dune.director = "Дени Вильнёв"
        dune.cast_json = json.dumps(["Тимоти Шаламе", "Зендея"])
        dune.year = 2024
        dune.description = "Пол Атрейдес защищает Арракис."
        dune.title_uz = "Dyuna: Ikkinchi qism"
        dune.genre_uz = "Fantastika"

        panda = movie_row("Кунг-фу Панда 4")
        panda.genre = "Мультфильм"
        panda.country = "США, Китай"
        panda.director = "Майк Митчелл"
        panda.cast_json = json.dumps(["Джек Блэк"])
        panda.year = 2024

        session.add_all([dune, panda])
        await session.flush()
        session.add_all([
            Show(movie_id=dune.id, show_date=SHOW_DATE, start_time="19:00"),
            Show(movie_id=panda.id, show_date=SHOW_DATE, start_time="12:00"),
        ])
        await session.commit()
    return None


async def test_empty_query_returns_the_whole_catalog(client, library):
    assert len(await _catalog(client)) == 3
    assert len(await _catalog(client, q="")) == 3
    assert len(await _catalog(client, q="   ")) == 3


async def test_search_by_full_and_partial_title(client, library):
    assert await _catalog(client, q="Дюна: Часть 2") == ["Дюна: Часть 2"]
    assert await _catalog(client, q="Кунг") == ["Кунг-фу Панда 4"]
    assert await _catalog(client, q="анда") == ["Кунг-фу Панда 4"]


async def test_search_is_case_insensitive_for_cyrillic(client, library):
    """SQLite's LIKE only folds ASCII, which is why matching happens in Python."""
    assert await _catalog(client, q="дюна") == ["Дюна: Часть 2"]
    assert await _catalog(client, q="ДЮНА") == ["Дюна: Часть 2"]


async def test_search_by_genre(client, library):
    assert await _catalog(client, q="Мультфильм") == ["Кунг-фу Панда 4"]
    assert await _catalog(client, q="фантастика") == ["Дюна: Часть 2"]


async def test_search_by_director_cast_country_and_year(client, library):
    assert await _catalog(client, q="Вильнёв") == ["Дюна: Часть 2"]
    assert await _catalog(client, q="Зендея") == ["Дюна: Часть 2"]
    assert await _catalog(client, q="Джек Блэк") == ["Кунг-фу Панда 4"]
    assert await _catalog(client, q="Китай") == ["Кунг-фу Панда 4"]
    # Every fixture movie is from 2024, so a year query matches the whole library.
    assert sorted(await _catalog(client, q="2024")) == [
        "Дюна: Часть 2", "Кунг-фу Панда 4", "Тестовый фильм",
    ]


async def test_search_by_description(client, library):
    assert await _catalog(client, q="Арракис") == ["Дюна: Часть 2"]


async def test_search_matches_the_requested_language(client, library):
    """The Uzbek title is only searchable in Uzbek mode."""
    assert await _catalog(client, q="Dyuna") == []
    assert await _catalog(client, lang="uz", q="Dyuna") == ["Dyuna: Ikkinchi qism"]
    assert await _catalog(client, lang="uz", q="Fantastika") == ["Dyuna: Ikkinchi qism"]


async def test_search_that_matches_nothing_returns_an_empty_list(client, library):
    assert await _catalog(client, q="Оппенгеймер") == []


async def test_search_combines_with_the_date_filter(client, library):
    """The date narrows first, then the query filters what is left."""
    assert sorted(await _catalog(client, date=SHOW_DATE)) == [
        "Дюна: Часть 2", "Кунг-фу Панда 4", "Тестовый фильм",
    ]
    assert await _catalog(client, date=SHOW_DATE, q="Панда") == ["Кунг-фу Панда 4"]

    empty_day = (date.today() + timedelta(days=30)).isoformat()
    assert await _catalog(client, date=empty_day, q="Панда") == []


async def test_overlong_query_is_rejected(client, library):
    response = await client.get("/api/movies", params={"q": "я" * 101})
    assert response.status_code == 422


async def test_only_new_filter(client, library):
    async with SessionLocal() as session:
        fresh = movie_row("Свежая премьера")
        fresh.is_new = True
        session.add(fresh)
        await session.commit()

    assert await _catalog(client, only_new="true") == ["Свежая премьера"]
    assert len(await _catalog(client)) == 4


async def test_only_new_respects_the_expiry_date(client):
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    async with SessionLocal() as session:
        still_new = movie_row("Ещё новинка")
        still_new.is_new, still_new.new_until = True, tomorrow
        expired = movie_row("Уже не новинка")
        expired.is_new, expired.new_until = True, yesterday
        session.add_all([still_new, expired])
        await session.commit()

    assert await _catalog(client, only_new="true") == ["Ещё новинка"]


async def test_only_new_combines_with_search(client, library):
    async with SessionLocal() as session:
        fresh = movie_row("Новинка про космос")
        fresh.is_new = True
        fresh.genre = "Фантастика"
        session.add(fresh)
        await session.commit()

    assert await _catalog(client, only_new="true", q="космос") == ["Новинка про космос"]
    assert await _catalog(client, only_new="true", q="Панда") == []
    # Without the flag the query alone still finds both science-fiction titles.
    assert sorted(await _catalog(client, q="Фантастика")) == ["Дюна: Часть 2", "Новинка про космос"]
