"""The admin is told about a new booking twice: in the panel, and in Telegram.

The panel notification is a database row and was always there.  What is checked
here is the live Bot API message that now goes out beside it -- and, just as
importantly, that no failure of that message can cost the cinema a booking.
"""
from __future__ import annotations

import json
import unicodedata

import httpx
import pytest
from sqlalchemy import select

from backend.core.db import SessionLocal
from backend.models import AdminNotification, Booking
from backend.services.telegram import new_booking_admin_message, notify_admins
from tests.conftest import (
    ADMIN_ID,
    BOT_TOKEN,
    OTHER_ID,
    SESSION,
    SHOW_DATE,
    USER_ID,
    auth_header,
    login,
)

CONTACT = {
    "first_name": "Иван",
    "last_name": "Петров",
    "phone": "+998 91 326 20 65",
    "telegram_username": "ivanp",
    "comment": "Нужны места рядом",
}


async def make_booking(client, movie, seats: list[str], token: str | None = None) -> httpx.Response:
    token = token or await login(client, USER_ID)
    payload = {"movie_id": movie.id, "show_date": SHOW_DATE, "session": SESSION, "seats": seats}
    hold = await client.post("/api/holds", json=payload, headers=auth_header(token))
    assert hold.status_code == 200, hold.text
    return await client.post(
        "/api/bookings/confirm", json={**payload, **CONTACT}, headers=auth_header(token)
    )


async def count_notifications() -> int:
    async with SessionLocal() as session:
        return len((await session.scalars(select(AdminNotification))).all())


# --- the happy path: both channels fire --------------------------------------


async def test_new_booking_messages_the_admin_in_telegram(client, movie, telegram_outbox):
    confirm = await make_booking(client, movie, ["1-1", "1-2"])
    assert confirm.status_code == 200, confirm.text

    assert len(telegram_outbox) == 1, "exactly one admin should have been messaged"
    request = telegram_outbox[0]
    assert str(request.url) == f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    assert request.method == "POST"

    body = json.loads(request.content)
    assert body["chat_id"] == ADMIN_ID

    text = body["text"]
    assert "Новая заявка на бронирование" in text
    assert movie.title in text
    assert SHOW_DATE in text and SESSION in text
    assert "1-1, 1-2" in text
    assert "Иван Петров" in text
    assert "+998913262065" in text
    assert "@ivanp" in text
    assert "Нужны места рядом" in text
    assert "60000" in text


async def test_the_admin_panel_row_is_still_created(client, movie, telegram_outbox):
    """Telegram is an addition, not a replacement: the panel must be unaffected."""
    assert (await make_booking(client, movie, ["2-1"])).status_code == 200
    assert await count_notifications() == 1
    assert len(telegram_outbox) == 1

    admin_token = await login(client, ADMIN_ID, "admin")
    dashboard = await client.get("/api/admin/dashboard", headers=auth_header(admin_token))
    assert dashboard.status_code == 200


async def test_every_configured_admin_is_messaged(client, movie, telegram_outbox, monkeypatch):
    from backend.core import config

    monkeypatch.setattr(config, "ADMIN_TELEGRAM_IDS", {ADMIN_ID, OTHER_ID})
    assert (await make_booking(client, movie, ["2-2"])).status_code == 200
    assert sorted(telegram_outbox.chat_ids()) == sorted([ADMIN_ID, OTHER_ID])


# --- a broken Telegram must never cost a booking ------------------------------


@pytest.mark.parametrize(
    "responder",
    [
        pytest.param(
            lambda request: (_ for _ in ()).throw(httpx.ConnectError("no route to host")),
            id="network-is-down",
        ),
        pytest.param(
            lambda request: (_ for _ in ()).throw(httpx.ReadTimeout("too slow")),
            id="telegram-times-out",
        ),
        pytest.param(
            lambda request: httpx.Response(403, json={"ok": False, "description": "bot was blocked"}),
            id="admin-never-started-the-chat",
        ),
        pytest.param(
            lambda request: httpx.Response(401, json={"ok": False, "description": "Unauthorized"}),
            id="token-is-invalid",
        ),
        pytest.param(
            lambda request: (_ for _ in ()).throw(RuntimeError("something unforeseen")),
            id="an-error-nobody-predicted",
        ),
    ],
)
async def test_a_failed_notification_never_rolls_back_the_booking(
    client, movie, telegram_outbox, responder
):
    telegram_outbox.responder = responder

    confirm = await make_booking(client, movie, ["3-1"])
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["status"] == "pending"

    # The booking and its panel notification are committed regardless.
    async with SessionLocal() as session:
        bookings = (await session.scalars(select(Booking))).all()
    assert len(bookings) == 1
    assert bookings[0].seats == "3-1"
    assert await count_notifications() == 1

    # And the seat really is taken, so the failure did not half-apply either.
    seats = await client.get(
        f"/api/sessions/{movie.id}/seats", params={"show_date": SHOW_DATE, "session_time": SESSION}
    )
    assert seats.json()["taken"] == ["3-1"]


async def test_an_empty_bot_token_skips_delivery_quietly(client, movie, telegram_outbox, monkeypatch):
    from backend.services import telegram

    # Logged in first: initData is validated with the same token, so blanking it
    # earlier would fail the login rather than the notification.
    token = await login(client, USER_ID)
    monkeypatch.setattr(telegram.config, "bot_token", lambda: "")
    assert (await make_booking(client, movie, ["3-2"], token)).status_code == 200
    assert telegram_outbox == []
    assert await count_notifications() == 1


async def test_no_configured_admin_skips_delivery_quietly(telegram_outbox, monkeypatch):
    from backend.core import config

    monkeypatch.setattr(config, "ADMIN_TELEGRAM_IDS", set())
    await notify_admins("Проверка")
    assert telegram_outbox == []


# --- the proposal answer notifies the admin too -------------------------------


async def test_answering_a_time_proposal_messages_the_admin(client, movie, telegram_outbox):
    token = await login(client, USER_ID)
    assert (await make_booking(client, movie, ["1-3"], token)).status_code == 200
    booking_id = (await client.get("/api/profile/bookings", headers=auth_header(token))).json()[0]["id"]

    admin_token = await login(client, ADMIN_ID, "admin")
    proposal = await client.patch(
        f"/api/admin/bookings/{booking_id}/decision",
        json={"action": "propose", "reason": "Зал занят", "proposed_session": "21:00"},
        headers=auth_header(admin_token),
    )
    assert proposal.status_code == 200, proposal.text

    telegram_outbox.clear()
    answer = await client.patch(
        f"/api/profile/bookings/{booking_id}/proposal",
        json={"action": "decline"},
        headers=auth_header(token),
    )
    assert answer.status_code == 200, answer.text

    assert telegram_outbox.chat_ids() == [ADMIN_ID]
    assert f"Клиент отказался от нового времени заявки #{booking_id}" in telegram_outbox.texts()[0]


# --- house style --------------------------------------------------------------


#: The variation selector and the zero-width joiner, written as escapes so this
#: file itself stays free of the characters it is policing.
EMOJI_MODIFIERS = "\uFE0F\u200D\u20E3"


def _emoji(text: str) -> list[str]:
    """Anything Unicode files under a pictographic category, plus the modifiers."""
    return [
        char
        for char in text
        if unicodedata.category(char) == "So"
        or char in EMOJI_MODIFIERS
        or ord(char) > 0x1F000
        or 0x2190 <= ord(char) <= 0x27BF
    ]


def test_the_admin_message_carries_no_emoji():
    booking = Booking(
        id=7,
        show_date=SHOW_DATE,
        session=SESSION,
        seats="1-1,1-2",
        total=60000,
        first_name="Иван",
        last_name="Петров",
        phone="+998913262065",
        telegram_username="ivanp",
        comment="Без смайликов",
    )
    text = new_booking_admin_message(booking, "Тестовый фильм")
    assert _emoji(text) == []
    assert text.startswith("Новая заявка на бронирование")
    assert "Заявка #7" in text


def test_a_booking_without_optional_fields_still_reads_sensibly():
    booking = Booking(
        id=8,
        show_date=SHOW_DATE,
        session=SESSION,
        seats="2-4",
        total=30000,
        first_name="",
        last_name="",
        phone="+998900000000",
        telegram_username="",
        comment="",
    )
    text = new_booking_admin_message(booking, "Фильм")
    assert "Без имени" in text
    assert "Telegram:" not in text
    assert "Комментарий:" not in text
