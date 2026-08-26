"""The administrator processes a request from the bot's own DM, with buttons.

The mini app's admin panel still exists, but the client asked for the everyday
workflow to live in Telegram itself: the notification the administrator
already gets carries real inline buttons -- start processing, confirm,
propose a time, decline -- so a request can be handled without opening the
Mini App at all. Under the buttons is the exact same decision logic the panel
uses (`apply_decision`); only the surface changed, and the panel keeps working
unmodified because `/api/admin/bookings/{id}/decision` now calls that same
function.
"""
from __future__ import annotations

import json
import unicodedata

import pytest
from sqlalchemy import select

from backend.core.config import DEFAULT_SLOT_TIMES
from backend.core.db import SessionLocal
from backend.models import Booking
from backend.services.bot_actions import handle_booking_callback
from backend.services.booking_decisions import (
    BookingNotFound,
    HallIsFull,
    ProposedTimeRequired,
    apply_decision,
)
from backend.services.telegram import admin_action_card, admin_action_keyboard, admin_propose_time_keyboard
from tests.conftest import ADMIN_ID, OTHER_ID, USER_ID, auth_header, login
from tests.test_generic_booking import book, hold


# --- the keyboard shape --------------------------------------------------------


def _callbacks(keyboard: dict) -> list[str]:
    return [button["callback_data"] for row in keyboard["inline_keyboard"] for button in row if "callback_data" in button]


def test_a_pending_request_offers_every_action():
    assert _callbacks(admin_action_keyboard(7, "pending")) == [
        "bk:contact:7", "bk:confirm:7", "bk:propose:7", "bk:decline:7",
    ]


def test_a_request_already_being_worked_does_not_offer_to_start_again():
    """`contacting` means the administrator is already on the phone."""
    assert _callbacks(admin_action_keyboard(7, "contacting")) == [
        "bk:confirm:7", "bk:propose:7", "bk:decline:7",
    ]


@pytest.mark.parametrize("status", ["confirmed", "cancelled", "watched"])
def test_a_settled_request_offers_no_action_at_all(status):
    assert _callbacks(admin_action_keyboard(7, status)) == [], (
        f"{status} is final; a button here could only relitigate it"
    )


def test_the_chat_button_opens_telegram_by_username():
    keyboard = admin_action_keyboard(7, "pending", telegram_username="@ivanp")
    urls = [button["url"] for row in keyboard["inline_keyboard"] for button in row if "url" in button]
    assert urls == ["https://t.me/ivanp"]


def test_the_chat_button_falls_back_to_the_telegram_id_without_a_username():
    keyboard = admin_action_keyboard(7, "pending", telegram_username="", telegram_id=555)
    urls = [button["url"] for row in keyboard["inline_keyboard"] for button in row if "url" in button]
    assert urls == ["tg://user?id=555"]


def test_no_chat_button_with_neither_a_username_nor_an_id():
    keyboard = admin_action_keyboard(7, "pending")
    assert not [button for row in keyboard["inline_keyboard"] for button in row if "url" in button]


def test_the_propose_keyboard_offers_every_fixed_time_and_a_way_back():
    keyboard = admin_propose_time_keyboard(7, list(DEFAULT_SLOT_TIMES))
    buttons = [button for row in keyboard["inline_keyboard"] for button in row]
    assert [button["callback_data"] for button in buttons[:-1]] == [
        f"bk:proposetime:7:{time}" for time in DEFAULT_SLOT_TIMES
    ]
    assert buttons[-1]["callback_data"] == "bk:cancelpropose:7"


# --- the card carries the facts and never an emoji -----------------------------


class _FakeResult:
    """Duck-types `DecisionResult` -- only the fields `admin_action_card` reads."""

    def __init__(self, **overrides):
        self.booking_id = 9
        self.status = "pending"
        self.proposed_session = ""
        self.admin_note = ""
        self.telegram_username = "ivanp"
        self.party_size = 3
        self.total = 90000
        self.phone = "+998913262065"
        self.show_date = "2026-08-27"
        self.session_time = "18:00"
        self.movie_title = None
        self.__dict__.update(overrides)


def test_the_card_has_no_emoji_matching_house_style():
    text = admin_action_card(_FakeResult())
    offenders = [char for char in text if unicodedata.category(char) == "So" or ord(char) > 0x1F000]
    assert offenders == [], f"an emoji slipped into the admin card: {offenders}"
    assert "Заявка #9" in text
    assert "Гостей: 3" in text
    assert "+998913262065" in text
    assert "согласуется" in text.lower(), "no film was ever promised in this flow"


def test_the_card_names_the_film_when_one_was_agreed():
    text = admin_action_card(_FakeResult(movie_title="Дюна"))
    assert "Дюна" in text


def test_the_card_shows_a_proposed_time_and_a_note():
    text = admin_action_card(_FakeResult(proposed_session="20:00", admin_note="Зал занят"))
    assert "20:00" in text
    assert "Зал занят" in text


# --- the new-request notification already carries working buttons ------------


async def test_the_new_request_message_carries_the_pending_keyboard(client, telegram_outbox):
    token = await login(client, USER_ID)
    booking = await book(client, token, 2)

    request = next(item for item in telegram_outbox if json.loads(item.content)["chat_id"] == ADMIN_ID)
    body = json.loads(request.content)
    keyboard = body["reply_markup"]
    assert _callbacks(keyboard) == [
        f"bk:contact:{booking['id']}", f"bk:confirm:{booking['id']}",
        f"bk:propose:{booking['id']}", f"bk:decline:{booking['id']}",
    ]


# --- apply_decision: the one place status changes, panel or bot --------------


async def test_confirming_notifies_the_viewer_and_settles_the_request(client):
    token = await login(client, USER_ID)
    booking = await book(client, token, 2)
    async with SessionLocal() as session:
        result = await apply_decision(session, booking["id"], "confirm")
    assert result.status == "confirmed"
    assert result.party_size == 2
    assert result.total == 60000
    assert "не закрепляется автоматически" in result.viewer_message


async def test_a_request_can_be_declined_with_a_reason(client):
    token = await login(client, USER_ID)
    booking = await book(client, token, 3)
    async with SessionLocal() as session:
        result = await apply_decision(session, booking["id"], "decline", reason="зал на ремонте")
    assert result.status == "cancelled"
    assert result.admin_note == "зал на ремонте"
    assert "зал на ремонте" in result.viewer_message


async def test_proposing_a_time_without_one_is_refused(client):
    token = await login(client, USER_ID)
    booking = await book(client, token, 2)
    async with SessionLocal() as session:
        with pytest.raises(ProposedTimeRequired):
            await apply_decision(session, booking["id"], "propose")


async def test_confirming_a_request_the_hall_can_no_longer_take_is_refused(client):
    """The panel's own regression, reproduced through `apply_decision`."""
    first = await login(client, USER_ID)
    full = await book(client, first, 12)
    async with SessionLocal() as session:
        await apply_decision(session, full["id"], "decline")

    second = await login(client, OTHER_ID, "other")
    await book(client, second, 12)

    async with SessionLocal() as session:
        with pytest.raises(HallIsFull):
            await apply_decision(session, full["id"], "confirm")


async def test_a_missing_booking_is_reported_by_name():
    async with SessionLocal() as session:
        with pytest.raises(BookingNotFound):
            await apply_decision(session, 999999, "confirm")


# --- the bot's own callback handler: propose, pick a time, done --------------


async def test_the_propose_button_shows_the_fixed_times(client):
    token = await login(client, USER_ID)
    booking = await book(client, token, 2)
    async with SessionLocal() as session:
        outcome = await handle_booking_callback(session, f"bk:propose:{booking['id']}")
    assert outcome.edit_text is None, "only the keyboard changes, not the card"
    assert [t.split(":", 1)[1] for t in _callbacks(outcome.edit_keyboard)[:-1]] == [
        f"proposetime:{booking['id']}:{time}" for time in DEFAULT_SLOT_TIMES
    ]


async def test_picking_a_proposed_time_settles_it_and_messages_the_viewer(client, telegram_outbox):
    token = await login(client, USER_ID)
    booking = await book(client, token, 2)
    telegram_outbox.clear()

    async with SessionLocal() as session:
        outcome = await handle_booking_callback(session, f"bk:proposetime:{booking['id']}:20:00")

    assert outcome.viewer_message and "20:00" in outcome.viewer_message
    assert outcome.viewer_telegram_id == USER_ID
    assert "Предложено время: 20:00" in outcome.edit_text
    # Proposing a time is not a decision: the request is still open, exactly
    # as the admin panel's own "propose" action never changed the status.
    assert _callbacks(outcome.edit_keyboard) == [
        f"bk:contact:{booking['id']}", f"bk:confirm:{booking['id']}",
        f"bk:propose:{booking['id']}", f"bk:decline:{booking['id']}",
    ]

    async with SessionLocal() as session:
        row = await session.get(Booking, booking["id"])
    assert row.proposed_session == "20:00"
    assert row.status == "pending"


async def test_cancelling_the_time_picker_returns_to_the_action_keyboard(client):
    token = await login(client, USER_ID)
    booking = await book(client, token, 2)
    async with SessionLocal() as session:
        outcome = await handle_booking_callback(session, f"bk:cancelpropose:{booking['id']}")
    assert _callbacks(outcome.edit_keyboard) == [
        f"bk:contact:{booking['id']}", f"bk:confirm:{booking['id']}",
        f"bk:propose:{booking['id']}", f"bk:decline:{booking['id']}",
    ]


async def test_confirming_through_the_bot_edits_the_card_and_messages_the_viewer(client, telegram_outbox):
    token = await login(client, USER_ID)
    booking = await book(client, token, 2)
    telegram_outbox.clear()

    async with SessionLocal() as session:
        outcome = await handle_booking_callback(session, f"bk:confirm:{booking['id']}")

    assert outcome.viewer_telegram_id == USER_ID
    assert outcome.viewer_message
    assert "Статус: Подтверждена" in outcome.edit_text
    assert _callbacks(outcome.edit_keyboard) == [], "a confirmed request offers no further action"


async def test_a_callback_for_a_vanished_booking_is_a_quiet_alert(client):
    async with SessionLocal() as session:
        outcome = await handle_booking_callback(session, "bk:confirm:999999")
    assert outcome.edit_text is None
    assert outcome.edit_keyboard is None
    assert outcome.show_alert is True
    assert outcome.alert
