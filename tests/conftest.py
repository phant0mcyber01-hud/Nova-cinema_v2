"""Test configuration.

Environment is set before importing `backend` because config.py reads it at
import time and db.py builds the engine from it.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlencode

import pytest

TEST_ROOT = Path(tempfile.gettempdir()) / "nova_cinema_tests"
TEST_ROOT.mkdir(parents=True, exist_ok=True)
TEST_DB = TEST_ROOT / "nova_test.db"
TEST_DB.unlink(missing_ok=True)

BOT_TOKEN = "123456:TEST-BOT-TOKEN"
ADMIN_ID = 111
USER_ID = 222
OTHER_ID = 333

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB.as_posix()}"
os.environ["JWT_SECRET"] = "test-jwt-secret"
os.environ["BOT_TOKEN"] = BOT_TOKEN
os.environ["ADMIN_TELEGRAM_IDS"] = str(ADMIN_ID)
os.environ["AUTO_CREATE_SCHEMA"] = "false"
os.environ["UPLOAD_DIR"] = str(TEST_ROOT / "uploads")
os.environ["CORS_ORIGINS"] = "https://example.test/,https://second.test"

import httpx  # noqa: E402

from backend.core.db import Base, SessionLocal, engine  # noqa: E402
from backend.main import app  # noqa: E402
from backend.models import Movie, Show  # noqa: E402


def telegram_init_data(telegram_id: int, username: str = "tester", first_name: str = "Test") -> str:
    """Build initData that passes the real server-side HMAC check."""
    values = {
        "auth_date": str(int(time.time())),
        "user": json.dumps(
            {"id": telegram_id, "username": username, "first_name": first_name},
            separators=(",", ":"),
            ensure_ascii=False,
        ),
    }
    check = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    signature = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode({**values, "hash": signature})


SHOW_DATE = (date.today() + timedelta(days=1)).isoformat()
SESSION = "19:00"


def movie_row(title: str = "Тестовый фильм") -> Movie:
    return Movie(
        title=title,
        genre="Драма",
        description="Описание",
        poster="https://example.test/poster.jpg",
        trailer_id="abcdefghijk",
        duration=100,
        age=12,
        year=2024,
        country="Узбекистан",
        director="Режиссёр",
        imdb=7.5,
        kinopoisk=7.0,
    )


@pytest.fixture(autouse=True)
async def database():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://nova.test") as instance:
        yield instance


@pytest.fixture
async def movie():
    """A published movie with one active screening tomorrow at 19:00."""
    async with SessionLocal() as session:
        item = movie_row()
        session.add(item)
        await session.flush()
        session.add(Show(movie_id=item.id, show_date=SHOW_DATE, start_time=SESSION))
        await session.commit()
        await session.refresh(item)
        return item


async def login(client: httpx.AsyncClient, telegram_id: int, username: str = "tester") -> str:
    response = await client.post(
        "/api/auth/telegram", json={"init_data": telegram_init_data(telegram_id, username)}
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
