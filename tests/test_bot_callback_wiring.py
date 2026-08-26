"""`bot.py`'s own wiring around `handle_booking_callback`.

`test_admin_bot_actions.py` proves the decision logic; this file proves the
aiogram glue around it doesn't choke on the one case that is easy to get
wrong: a settled request's keyboard is empty, and aiogram's own
`InlineKeyboardMarkup` refuses an empty `inline_keyboard` list outright.
"""
from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup

from bot import _to_aiogram_markup


def test_a_populated_keyboard_survives_the_round_trip():
    keyboard = {"inline_keyboard": [[{"text": "Подтвердить", "callback_data": "bk:confirm:1"}]]}
    markup = _to_aiogram_markup(keyboard)
    assert isinstance(markup, InlineKeyboardMarkup)
    assert markup.inline_keyboard[0][0].callback_data == "bk:confirm:1"


def test_a_url_button_survives_the_round_trip():
    keyboard = {"inline_keyboard": [[{"text": "Открыть чат", "url": "https://t.me/ivanp"}]]}
    markup = _to_aiogram_markup(keyboard)
    assert markup.inline_keyboard[0][0].url == "https://t.me/ivanp"


def test_an_empty_keyboard_becomes_none_not_a_crash():
    """A settled request (confirmed/cancelled/watched) offers no action at all."""
    assert _to_aiogram_markup({"inline_keyboard": []}) is None


def test_none_stays_none():
    assert _to_aiogram_markup(None) is None
