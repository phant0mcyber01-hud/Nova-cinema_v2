"""The catalog has to group films the way somebody browsing expects.

Two things the client asked for and the old code did not do:

* a film carries several genres in one string ("Фантастика, Боевик"), and each
  of them is a real genre — not one label nobody will ever click;
* "похожие фильмы" must actually be similar. Returning the first two rows in
  the catalog put a cartoon under a horror film.
"""
from __future__ import annotations

import pytest

from backend.core.db import SessionLocal
from backend.services.catalog import split_genres
from tests.conftest import movie_row


@pytest.fixture()
async def catalog():
    """A catalog where the obvious neighbour is not the first row."""
    async with SessionLocal() as session:
        rows = [
            movie_row("Мультик про кота", genre="Мультфильм"),
            movie_row("Другой мультик", genre="Мультфильм"),
            movie_row("Космическая одиссея", genre="Фантастика, Боевик"),
            movie_row("Ужас в лесу", genre="Ужасы"),
            movie_row("Ужас в подвале", genre="Ужасы"),
            movie_row("Боевик в городе", genre="Боевик"),
        ]
        session.add_all(rows)
        await session.commit()
        return {row.title: row.id for row in rows}


# --- several genres in one field ---------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Фантастика, Боевик", ["Фантастика", "Боевик"]),
        ("Ужасы", ["Ужасы"]),
        ("Драма,  Комедия ,", ["Драма", "Комедия"]),
        ("", []),
    ],
)
def test_a_multi_genre_field_is_read_as_several_genres(value, expected):
    assert split_genres(value) == expected


async def test_the_genre_list_offers_each_genre_separately(client, catalog):
    movies = (await client.get("/api/movies")).json()
    genres = {genre for movie in movies for genre in split_genres(movie["genre"])}
    assert "Фантастика" in genres and "Боевик" in genres, (
        f'"Фантастика, Боевик" must be two genres, got {sorted(genres)}'
    )
    assert "Фантастика, Боевик" not in genres


# --- similar films ------------------------------------------------------------


async def test_similar_films_share_a_genre(client, catalog):
    detail = (await client.get(f"/api/movies/{catalog['Ужас в лесу']}")).json()
    similar = detail["similar_movies"]
    assert similar, "another horror film exists, so it must be offered"
    for item in similar:
        assert set(split_genres(item["genre"])) & {"Ужасы"}, (
            f"{item['title']} ({item['genre']}) is not similar to a horror film"
        )


async def test_nothing_is_offered_rather_than_something_unrelated(client, catalog):
    """A cartoon under a horror film is worse than an empty block."""
    detail = (await client.get(f"/api/movies/{catalog['Космическая одиссея']}")).json()
    for item in detail["similar_movies"]:
        assert set(split_genres(item["genre"])) & {"Фантастика", "Боевик"}, (
            f"{item['title']} ({item['genre']}) shares no genre and must not be shown"
        )


async def test_a_film_sharing_one_of_several_genres_counts_as_similar(client, catalog):
    detail = (await client.get(f"/api/movies/{catalog['Боевик в городе']}")).json()
    titles = [item["title"] for item in detail["similar_movies"]]
    assert "Космическая одиссея" in titles, (
        f'a "Фантастика, Боевик" film shares Боевик and must be offered, got {titles}'
    )


async def test_a_film_is_never_similar_to_itself(client, catalog):
    movie_id = catalog["Мультик про кота"]
    detail = (await client.get(f"/api/movies/{movie_id}")).json()
    assert movie_id not in [item["id"] for item in detail["similar_movies"]]
