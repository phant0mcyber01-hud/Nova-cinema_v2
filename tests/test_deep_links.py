"""Stage 8: share links — payload format, and every way a link can go stale."""
from __future__ import annotations

import pytest

from backend.core.db import SessionLocal
from backend.models import Movie
from backend.services.deep_link import movie_id_from_payload, movie_payload, share_link
from tests.conftest import ADMIN_ID, auth_header, login, movie_row


# --- payload format ----------------------------------------------------------


@pytest.mark.parametrize(
    "payload,expected",
    [
        ("movie_1", 1),
        ("movie_42", 42),
        ("  movie_7  ", 7),
        ("movie_000123", 123),
    ],
)
def test_valid_payload_yields_a_movie_id(payload, expected):
    assert movie_id_from_payload(payload) == expected


@pytest.mark.parametrize(
    "payload",
    [
        None,
        "",
        "   ",
        "movie_",
        "movie_0",
        "movie_abc",
        "movie_-1",
        "movie_1.5",
        "MOVIE_1",
        "film_1",
        "movie_1_extra",
        "prefix_movie_1",
        "movie_1234567890123",
        "'; DROP TABLE movies; --",
    ],
)
def test_malformed_payload_is_rejected(payload):
    """A wrong link must degrade to the catalog, never crash the launch."""
    assert movie_id_from_payload(payload) is None


def test_payload_round_trips():
    assert movie_id_from_payload(movie_payload(99)) == 99


def test_share_link_shape():
    assert share_link("novacinema_bot", 5) == "https://t.me/novacinema_bot?startapp=movie_5"
    assert share_link("@novacinema_bot", 5) == "https://t.me/novacinema_bot?startapp=movie_5"
    assert share_link("  @novacinema_bot ", 5) == "https://t.me/novacinema_bot?startapp=movie_5"


def test_share_link_is_empty_until_the_bot_handle_is_configured():
    """Better an absent button than a link to t.me/?startapp=…"""
    assert share_link("", 5) == ""
    assert share_link(None, 5) == ""
    assert share_link("   ", 5) == ""


# --- the card the link points at ---------------------------------------------


async def _set_bot_handle(client, handle: str) -> None:
    admin = await login(client, ADMIN_ID, "admin")
    current = (await client.get("/api/admin/settings", headers=auth_header(admin))).json()
    current.pop("hall_seats", None)
    current.pop("updated_at", None)
    current["bot_username"] = handle
    response = await client.put("/api/admin/settings", json=current, headers=auth_header(admin))
    assert response.status_code == 200, response.text


async def test_movie_card_carries_the_share_link(client, movie):
    await _set_bot_handle(client, "novacinema_bot")
    data = (await client.get(f"/api/movies/{movie.id}")).json()
    assert data["share_link"] == f"https://t.me/novacinema_bot?startapp=movie_{movie.id}"


async def test_share_link_is_empty_when_the_bot_is_not_configured(client, movie):
    assert (await client.get(f"/api/movies/{movie.id}")).json()["share_link"] == ""


async def test_link_to_a_deleted_movie_returns_404(client, movie):
    admin = await login(client, ADMIN_ID, "admin")
    assert (await client.delete(f"/api/admin/movies/{movie.id}", headers=auth_header(admin))).status_code == 200
    assert (await client.get(f"/api/movies/{movie.id}")).status_code == 404


async def test_link_to_an_unpublished_movie_returns_404(client, movie):
    """A movie hidden by the admin must behave like a stale link, not leak."""
    async with SessionLocal() as session:
        item = await session.get(Movie, movie.id)
        item.is_published = False
        await session.commit()

    assert (await client.get(f"/api/movies/{movie.id}")).status_code == 404
    assert [item["id"] for item in (await client.get("/api/movies")).json()] == []


async def test_link_to_a_never_existing_movie_returns_404(client):
    assert (await client.get("/api/movies/999999")).status_code == 404


async def test_link_with_a_non_numeric_id_is_rejected(client):
    assert (await client.get("/api/movies/abc")).status_code == 422


async def test_republished_movie_becomes_reachable_again(client, movie):
    async with SessionLocal() as session:
        item = await session.get(Movie, movie.id)
        item.is_published = False
        await session.commit()
    assert (await client.get(f"/api/movies/{movie.id}")).status_code == 404

    async with SessionLocal() as session:
        item = await session.get(Movie, movie.id)
        item.is_published = True
        await session.commit()
    assert (await client.get(f"/api/movies/{movie.id}")).status_code == 200


async def test_share_link_follows_a_bot_handle_change(client, movie):
    await _set_bot_handle(client, "old_bot")
    assert "old_bot" in (await client.get(f"/api/movies/{movie.id}")).json()["share_link"]

    await _set_bot_handle(client, "new_bot")
    link = (await client.get(f"/api/movies/{movie.id}")).json()["share_link"]
    assert link == f"https://t.me/new_bot?startapp=movie_{movie.id}"


async def test_second_movie_gets_its_own_link(client, movie):
    await _set_bot_handle(client, "novacinema_bot")
    async with SessionLocal() as session:
        other = movie_row("Другой фильм")
        session.add(other)
        await session.commit()
        await session.refresh(other)
        other_id = other.id

    first = (await client.get(f"/api/movies/{movie.id}")).json()["share_link"]
    second = (await client.get(f"/api/movies/{other_id}")).json()["share_link"]
    assert first != second
    assert second.endswith(f"movie_{other_id}")
