"""Stage 17: the Telegram contract, and never trusting the client.

Spec: validate initData on the backend and do not trust anything that arrives
from the frontend alone.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import timedelta
from urllib.parse import urlencode

import jwt

from backend.core import config
from backend.core.db import utcnow
from tests.conftest import (
    ADMIN_ID,
    BOT_TOKEN,
    SESSION,
    SHOW_DATE,
    USER_ID,
    auth_header,
    login,
    telegram_init_data,
)


def _signed_init_data(payload: dict[str, str]) -> str:
    check = "\n".join(f"{key}={payload[key]}" for key in sorted(payload))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    signature = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode({**payload, "hash": signature})


def _user_field(telegram_id: int) -> str:
    return json.dumps(
        {"id": telegram_id, "username": "tester", "first_name": "Test"},
        separators=(",", ":"),
        ensure_ascii=False,
    )


# --- initData is validated on the server -------------------------------------


async def test_valid_init_data_is_accepted(client):
    response = await client.post(
        "/api/auth/telegram", json={"init_data": telegram_init_data(USER_ID)}
    )
    assert response.status_code == 200


async def test_init_data_without_a_signature_is_refused(client):
    payload = {"auth_date": str(int(time.time())), "user": _user_field(USER_ID)}
    response = await client.post("/api/auth/telegram", json={"init_data": urlencode(payload)})
    assert response.status_code == 401


async def test_tampered_user_breaks_the_signature(client):
    """Changing the id after signing must invalidate the whole payload."""
    good = telegram_init_data(USER_ID)
    forged = good.replace(str(USER_ID), str(ADMIN_ID))
    response = await client.post("/api/auth/telegram", json={"init_data": forged})
    assert response.status_code == 401


async def test_signature_from_a_different_bot_token_is_refused(client):
    payload = {"auth_date": str(int(time.time())), "user": _user_field(USER_ID)}
    check = "\n".join(f"{key}={payload[key]}" for key in sorted(payload))
    secret = hmac.new(b"WebAppData", b"999999:SOMEONE-ELSES-BOT", hashlib.sha256).digest()
    signature = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    response = await client.post(
        "/api/auth/telegram", json={"init_data": urlencode({**payload, "hash": signature})}
    )
    assert response.status_code == 401


async def test_stale_init_data_is_refused(client):
    """A correctly signed payload still expires — replaying it must not work."""
    stale = int(time.time()) - config.TELEGRAM_AUTH_MAX_AGE_SECONDS - 60
    init_data = _signed_init_data({"auth_date": str(stale), "user": _user_field(USER_ID)})
    response = await client.post("/api/auth/telegram", json={"init_data": init_data})
    assert response.status_code == 401


async def test_init_data_without_a_user_is_refused(client):
    init_data = _signed_init_data({"auth_date": str(int(time.time()))})
    response = await client.post("/api/auth/telegram", json={"init_data": init_data})
    assert response.status_code == 401


# --- the client cannot promote itself ----------------------------------------


async def test_a_token_claiming_admin_does_not_grant_admin(client):
    """The role is recomputed from ADMIN_TELEGRAM_IDS, never read from the token."""
    await login(client, USER_ID)  # create the row
    forged = jwt.encode(
        {"sub": "1", "role": "admin", "exp": utcnow() + timedelta(hours=1)},
        config.JWT_SECRET,
        algorithm=config.JWT_ALGORITHM,
    )
    assert (await client.get("/api/admin/dashboard", headers=auth_header(forged))).status_code == 403


async def test_a_token_signed_with_another_secret_is_refused(client):
    await login(client, USER_ID)
    forged = jwt.encode(
        {"sub": "1", "role": "admin", "exp": utcnow() + timedelta(hours=1)},
        "not-the-real-secret",
        algorithm=config.JWT_ALGORITHM,
    )
    assert (await client.get("/api/profile", headers=auth_header(forged))).status_code == 401


async def test_admin_role_follows_the_configured_ids(client):
    """The response says what the server decided, not what the client asked for."""
    body = (
        await client.post("/api/auth/telegram", json={"init_data": telegram_init_data(USER_ID)})
    ).json()
    assert body["user"]["role"] == "user"

    admin_body = (
        await client.post(
            "/api/auth/telegram", json={"init_data": telegram_init_data(ADMIN_ID, "admin")}
        )
    ).json()
    assert admin_body["user"]["role"] == "admin"


async def test_protected_endpoints_refuse_an_absent_token(client, movie):
    payload = {"movie_id": movie.id, "show_date": SHOW_DATE, "session": SESSION, "seats": ["1-1"]}
    for path, method in (
        ("/api/profile", "get"),
        ("/api/profile/bookings", "get"),
        ("/api/admin/dashboard", "get"),
    ):
        response = await getattr(client, method)(path)
        assert response.status_code == 401, path
    assert (await client.post("/api/holds", json=payload)).status_code == 401


async def test_a_viewer_cannot_read_the_admin_surface(client):
    token = await login(client, USER_ID)
    for path in (
        "/api/admin/dashboard",
        "/api/admin/bookings",
        "/api/admin/settings",
        "/api/admin/reviews",
        "/api/admin/gallery",
    ):
        assert (await client.get(path, headers=auth_header(token))).status_code == 403, path
