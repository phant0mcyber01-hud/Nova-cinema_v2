"""Minimal first-run seed used only when AUTO_CREATE_SCHEMA is enabled.

The full demo catalog lives in the standalone seed_movies.py script.
"""
from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from datetime import date, timedelta

from backend.core.config import DEFAULT_BOOKING_DAYS_AHEAD
from backend.models import CinemaSettings, Movie, Show

SEED_MOVIES: list[dict[str, object]] = [
    {
        "title": "Дюна: Часть 2",
        "title_uz": "Dyuna: Ikkinchi qism",
        "genre_uz": "Fantastika",
        "country_uz": "AQSH, Kanada",
        "director_uz": "Deni Vilnyov",
        "description_uz": "Pol Atreydes Chani va fremenlar bilan birlashib, Arrakisni himoya qiladi.",
        "genre": "Фантастика",
        "duration": 166,
        "age": 12,
        "year": 2024,
        "country": "США, Канада",
        "director": "Дени Вильнёв",
        "cast_json": json.dumps(["Тимоти Шаламе", "Зендея", "Ребекка Фергюсон"]),
        "poster": "https://image.tmdb.org/t/p/w780/1pdfLvkbY9ohJlCjQH2CZjjYVvJ.jpg",
        "trailer_id": "Way9Dexny3w",
        "gallery_json": json.dumps(
            [
                "https://image.tmdb.org/t/p/w1280/8b8R8l88Qje9dn9OE8PY05Nxl1X.jpg",
                "https://image.tmdb.org/t/p/w1280/xOMo8BRK7PfcJv9JCnx7s5hj0PX.jpg",
            ]
        ),
        "imdb": 8.6,
        "kinopoisk": 8.7,
        "description": "Пол Атрейдес объединяется с Чани и фременами, чтобы защитить Арракис.",
        "times": ["12:00", "15:30", "19:00", "22:15"],
    },
    {
        "title": "Кунг-фу Панда 4",
        "title_uz": "Kung-fu Panda 4",
        "genre_uz": "Multfilm",
        "country_uz": "AQSH, Xitoy",
        "director_uz": "Mayk Mitchell",
        "description_uz": "Po oʻziga voris izlaydi va epchil tulki Chjenni uchratadi.",
        "genre": "Мультфильм",
        "duration": 94,
        "age": 6,
        "year": 2024,
        "country": "США, Китай",
        "director": "Майк Митчелл",
        "cast_json": json.dumps(["Джек Блэк", "Аквафина", "Виола Дэвис"]),
        "poster": "https://image.tmdb.org/t/p/w780/kDp1vUBnMpe8ak4rjgl3cLELqjU.jpg",
        "trailer_id": "_inKs4eeHiI",
        "gallery_json": json.dumps(["https://image.tmdb.org/t/p/w1280/kDp1vUBnMpe8ak4rjgl3cLELqjU.jpg"]),
        "imdb": 6.3,
        "kinopoisk": 7.5,
        "description": "По ищет преемника и встречает ловкую лисицу Чжэнь.",
        "times": ["10:00", "13:15", "16:30"],
    },
    {
        "title": "Оппенгеймер",
        "title_uz": "Oppengeymer",
        "genre_uz": "Drama",
        "country_uz": "AQSH, Buyuk Britaniya",
        "director_uz": "Kristofer Nolan",
        "description_uz": "Fizik Robert Oppengeymer va atom bombasi yaratilishi tarixi.",
        "genre": "Драма",
        "duration": 180,
        "age": 18,
        "year": 2023,
        "country": "США, Великобритания",
        "director": "Кристофер Нолан",
        "cast_json": json.dumps(["Киллиан Мёрфи", "Эмили Блант", "Мэтт Дэймон"]),
        "poster": "https://image.tmdb.org/t/p/w780/8Gxv8gSFCU0XGDykEGv7zR1n2ua.jpg",
        "trailer_id": "uYPbbksJxIg",
        "gallery_json": json.dumps(["https://image.tmdb.org/t/p/w1280/8Gxv8gSFCU0XGDykEGv7zR1n2ua.jpg"]),
        "imdb": 8.6,
        "kinopoisk": 8.2,
        "description": "История физика Роберта Оппенгеймера и создания атомной бомбы.",
        "times": ["14:00", "17:30", "21:00"],
    },
]


async def seed(session: AsyncSession) -> None:
    """Create the settings row and, on an empty catalog, a few demo screenings."""
    if await session.get(CinemaSettings, 1) is None:
        session.add(CinemaSettings(id=1))
        await session.commit()
    if (await session.scalar(select(Movie.id).limit(1))) is not None:
        return
    window = [
        (date.today() + timedelta(days=offset)).isoformat()
        for offset in range(DEFAULT_BOOKING_DAYS_AHEAD)
    ]
    for item in SEED_MOVIES:
        payload = dict(item)
        times = payload.pop("times", [])
        movie = Movie(**payload)
        session.add(movie)
        await session.flush()
        session.add_all(
            Show(movie_id=movie.id, show_date=show_date, start_time=start_time)
            for show_date in window
            for start_time in times
        )
    await session.commit()
