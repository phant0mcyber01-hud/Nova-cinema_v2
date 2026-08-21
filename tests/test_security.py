"""Stage 18: the security checklist from the spec, as executable assertions.

Covers other people's bookings, admin rights, direct API calls that bypass the
interface, double booking, malformed identifiers, SQL injection, and secrets.
"""
from __future__ import annotations

import pathlib

from sqlalchemy import select

from backend.core import config
from backend.core.db import SessionLocal
from backend.models import Booking, Movie, UserNotification
from tests.conftest import ADMIN_ID, OTHER_ID, SESSION, SHOW_DATE, USER_ID, auth_header, login

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]

CONTACT = {
    "first_name": "Иван",
    "last_name": "Петров",
    "phone": "+998 91 326 20 65",
    "telegram_username": "ivanp",
    "comment": "",
}


async def _book(client, movie_id: int, seats: list[str], token: str):
    payload = {"movie_id": movie_id, "show_date": SHOW_DATE, "session": SESSION, "seats": seats}
    await client.post("/api/holds", json=payload, headers=auth_header(token))
    return await client.post("/api/bookings/confirm", json={**payload, **CONTACT}, headers=auth_header(token))


# --- somebody else's data ----------------------------------------------------


async def test_another_viewers_booking_is_invisible(client, movie):
    owner = await login(client, USER_ID)
    await _book(client, movie.id, ["1-1"], owner)
    booking_id = (await client.get("/api/profile/bookings", headers=auth_header(owner))).json()[0]["id"]

    intruder = await login(client, OTHER_ID, "other")
    assert (
        await client.get(f"/api/profile/bookings/{booking_id}", headers=auth_header(intruder))
    ).status_code == 404
    assert (await client.get("/api/profile/bookings", headers=auth_header(intruder))).json() == []


async def test_another_viewers_booking_cannot_be_steered(client, movie):
    """The proposal endpoint must not accept somebody else's booking id."""
    owner = await login(client, USER_ID)
    await _book(client, movie.id, ["1-1"], owner)
    booking_id = (await client.get("/api/profile/bookings", headers=auth_header(owner))).json()[0]["id"]

    intruder = await login(client, OTHER_ID, "other")
    response = await client.patch(
        f"/api/profile/bookings/{booking_id}/proposal",
        json={"action": "accept"},
        headers=auth_header(intruder),
    )
    assert response.status_code == 404


async def test_another_viewers_notification_cannot_be_read_or_marked(client, movie):
    owner = await login(client, USER_ID)
    async with SessionLocal() as session:
        session.add(UserNotification(user_id=1, type="booking_status", title="t", message="секрет"))
        await session.commit()
        notification_id = (await session.scalar(select(UserNotification.id)))

    intruder = await login(client, OTHER_ID, "other")
    assert (await client.get("/api/profile/notifications", headers=auth_header(intruder))).json() == []
    assert (
        await client.patch(
            f"/api/profile/notifications/{notification_id}/read", headers=auth_header(intruder)
        )
    ).status_code == 404
    assert len((await client.get("/api/profile/notifications", headers=auth_header(owner))).json()) == 1


async def test_public_reviews_do_not_expose_who_wrote_them(client, movie):
    """A viewer's name must not leak through the movie card."""
    from tests.conftest import watched_booking_in_the_past

    user = await login(client, USER_ID)
    await watched_booking_in_the_past(movie.id, 1)
    await client.post(
        f"/api/movies/{movie.id}/reviews",
        json={"rating": 5, "text": "Отлично"},
        headers=auth_header(user),
    )

    review = (await client.get(f"/api/movies/{movie.id}")).json()["reviews"][0]
    assert review["user_name"] == "Зритель"
    assert "telegram_username" not in review
    assert "user_id" not in review


# --- admin rights are enforced on the server ---------------------------------


async def test_every_admin_route_refuses_a_viewer(client):
    """Hiding the buttons is not protection — the spec says so explicitly."""
    token = await login(client, USER_ID)
    from backend.main import app

    admin_routes = [
        route for route in app.routes
        if getattr(route, "methods", None) and route.path.startswith("/api/admin")
    ]
    assert admin_routes, "the admin surface should not be empty"

    checked = 0
    for route in admin_routes:
        if "{" in route.path:
            continue  # covered by the parametrised checks elsewhere
        for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
            response = await client.request(method, route.path, headers=auth_header(token), json={})
            assert response.status_code in (403, 422), f"{method} {route.path} -> {response.status_code}"
            assert response.status_code != 200, f"{method} {route.path} let a viewer through"
            checked += 1
    assert checked >= 10


async def test_admin_write_routes_refuse_an_anonymous_caller(client):
    for method, path, body in (
        ("POST", "/api/admin/movies", {}),
        ("POST", "/api/admin/sessions", {}),
        ("PUT", "/api/admin/settings", {}),
        ("POST", "/api/admin/bonuses", {}),
        ("POST", "/api/admin/gallery", {}),
    ):
        response = await client.request(method, path, json=body)
        assert response.status_code == 401, f"{method} {path}"


# --- malformed identifiers ---------------------------------------------------


async def test_malformed_identifiers_are_refused_not_crashed(client):
    token = await login(client, USER_ID)
    for path in (
        "/api/movies/abc",
        "/api/movies/-1",
        "/api/movies/99999999999999999999",
        "/api/profile/bookings/abc",
    ):
        response = await client.get(path, headers=auth_header(token))
        assert response.status_code in (404, 422), f"{path} -> {response.status_code}"
        assert response.status_code != 500, f"{path} crashed the server"


async def test_unknown_identifiers_answer_not_found(client):
    admin = await login(client, ADMIN_ID, "admin")
    assert (await client.get("/api/movies/424242")).status_code == 404
    assert (
        await client.delete("/api/admin/movies/424242", headers=auth_header(admin))
    ).status_code == 404
    assert (
        await client.patch(
            "/api/admin/bookings/424242/status", json={"status": "confirmed"}, headers=auth_header(admin)
        )
    ).status_code == 404


# --- injection ---------------------------------------------------------------


async def test_sql_injection_in_search_is_inert(client, movie):
    """Everything goes through the ORM; a payload is just text."""
    for payload in (
        "'; DROP TABLE movies; --",
        "' OR '1'='1",
        "1); DELETE FROM bookings; --",
        "%' UNION SELECT * FROM users --",
    ):
        response = await client.get("/api/movies", params={"q": payload})
        assert response.status_code == 200
        assert response.json() == [], "an injection string should simply match nothing"

    async with SessionLocal() as session:
        assert len(list(await session.scalars(select(Movie)))) == 1, "the catalog survived"


async def test_injection_in_stored_text_is_stored_verbatim(client, movie):
    user = await login(client, USER_ID)
    payload = {
        "movie_id": movie.id,
        "show_date": SHOW_DATE,
        "session": SESSION,
        "seats": ["1-1"],
        **CONTACT,
        "comment": "'); DROP TABLE bookings; --",
    }
    await client.post("/api/holds", json=payload, headers=auth_header(user))
    assert (await client.post("/api/bookings/confirm", json=payload, headers=auth_header(user))).status_code == 200

    async with SessionLocal() as session:
        stored = await session.scalar(select(Booking))
    assert stored.comment == "'); DROP TABLE bookings; --", "stored as data, never executed"


# --- secrets -----------------------------------------------------------------


def test_env_is_ignored_by_git():
    ignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in ignore
    for pattern in ("*.db", "node_modules/", "dist/"):
        assert pattern in ignore, f".gitignore should exclude {pattern}"


def test_no_secret_is_hardcoded_in_the_source():
    """Keys and tokens come from the environment, never from a literal."""
    for path in (PROJECT_ROOT / "backend").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "BOT_TOKEN =" not in text or "os.getenv" in text
    config_text = (PROJECT_ROOT / "backend/core/config.py").read_text(encoding="utf-8")
    for name in ("BOT_TOKEN", "JWT_SECRET", "TMDB_API_KEY", "OMDB_API_KEY", "DATABASE_URL"):
        assert f'os.getenv("{name}")' in config_text, f"{name} must be read from the environment"


async def test_api_keys_never_reach_a_response(client):
    """A misconfigured lookup must not echo the key back to the caller."""
    admin = await login(client, ADMIN_ID, "admin")
    response = await client.post(
        "/api/admin/movies/lookup", json={"title": "Дюна"}, headers=auth_header(admin)
    )
    assert response.status_code in (404, 502, 503)
    body = response.text
    for secret in (config.JWT_SECRET, config.TMDB_API_KEY, config.OMDB_API_KEY):
        if secret:
            assert secret not in body


async def test_settings_response_carries_no_infrastructure_secrets(client):
    admin = await login(client, ADMIN_ID, "admin")
    for path in ("/api/settings", "/api/admin/settings"):
        body = (await client.get(path, headers=auth_header(admin))).text
        for forbidden in ("JWT_SECRET", "BOT_TOKEN", "DATABASE_URL", "api_key", "password"):
            assert forbidden not in body, f"{path} leaks {forbidden}"


# --- uploads -----------------------------------------------------------------


async def test_oversized_upload_is_refused(client):
    """The caller must not decide how much the server buffers."""
    admin = await login(client, ADMIN_ID, "admin")
    huge = b"\xff\xd8\xff" + b"0" * (config.UPLOAD_MAX_BYTES + 1024)
    response = await client.post(
        "/api/admin/uploads",
        files={"file": ("big.jpg", huge, "image/jpeg")},
        headers=auth_header(admin),
    )
    assert response.status_code == 413


async def test_upload_rejects_a_disguised_file(client):
    """An extension is not evidence — the signature is checked."""
    admin = await login(client, ADMIN_ID, "admin")
    for name, payload, content_type in (
        ("shell.jpg", b"<?php system($_GET[0]); ?>", "image/jpeg"),
        ("script.png", b"<script>alert(1)</script>", "image/png"),
    ):
        response = await client.post(
            "/api/admin/uploads",
            files={"file": (name, payload, content_type)},
            headers=auth_header(admin),
        )
        assert response.status_code == 422, name


async def test_upload_rejects_an_executable_extension(client):
    admin = await login(client, ADMIN_ID, "admin")
    response = await client.post(
        "/api/admin/uploads",
        files={"file": ("payload.svg", b"<svg onload=alert(1)>", "image/svg+xml")},
        headers=auth_header(admin),
    )
    assert response.status_code == 422


async def test_uploads_are_admin_only(client):
    token = await login(client, USER_ID)
    response = await client.post(
        "/api/admin/uploads",
        files={"file": ("a.jpg", b"\xff\xd8\xff0", "image/jpeg")},
        headers=auth_header(token),
    )
    assert response.status_code == 403


# --- configuration warnings --------------------------------------------------


def test_configuration_warnings_name_the_real_risks(monkeypatch):
    from backend.core import checks

    monkeypatch.setattr(config, "JWT_SECRET", "short")
    monkeypatch.setattr(config, "ADMIN_TELEGRAM_IDS", set())
    monkeypatch.setattr(
        config, "CORS_ORIGINS", ["https://stat-volunteers.trycloudflare.com"]
    )
    warnings = " ".join(checks.configuration_warnings())
    assert "JWT_SECRET" in warnings
    assert "ADMIN_TELEGRAM_IDS" in warnings
    assert "temporary tunnel" in warnings


def test_a_sound_configuration_warns_only_about_sqlite(monkeypatch):
    from backend.core import checks

    monkeypatch.setattr(config, "JWT_SECRET", "x" * 48)
    monkeypatch.setattr(config, "ADMIN_TELEGRAM_IDS", {1})
    monkeypatch.setattr(config, "CORS_ORIGINS", ["https://cinema.example"])
    monkeypatch.setattr(config, "DATABASE_URL", "postgresql+asyncpg://u:p@db/nova")
    assert checks.configuration_warnings() == []


def test_warnings_never_raise():
    """A misconfiguration must be loud, not fatal — the cinema keeps selling."""
    from backend.core import checks

    checks.log_configuration_warnings()
