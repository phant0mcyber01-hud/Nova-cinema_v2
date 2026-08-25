"""The bot's buttons must open screens the mini app still has.

Phase A removed the movie-bound booking route entirely: there is one entry to
the ticket flow, `/tickets`, and it books the hall rather than a film. A button
still pointing at `/booking/{movie_id}/date` opens a "not found" screen inside
Telegram, which is the one failure a viewer cannot work around.
"""
from __future__ import annotations

import pathlib
import re

import pytest

import bot as bot_module

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
APP_ROUTES = PROJECT_ROOT / "frontend" / "src" / "App.tsx"


def mini_app_paths() -> set[str]:
    """Every path the built router actually serves."""
    source = APP_ROUTES.read_text(encoding="utf-8")
    return set(re.findall(r'path="([^"]+)"', source))


def keyboard_paths(markup) -> list[str]:
    """The mini-app paths a keyboard opens, with the host stripped off."""
    paths = []
    for row in markup.inline_keyboard:
        for button in row:
            if button.web_app is None:
                continue
            without_scheme = re.sub(r"^https?://", "", button.web_app.url)
            _, _, path = without_scheme.partition("/")
            paths.append(f"/{path}")
    return paths


def matches_route(path: str, routes: set[str]) -> bool:
    """`/profile/bookings` is served by the `/profile/*` route."""
    clean = path.split("?")[0].rstrip("/") or "/"
    for route in routes:
        if route == "*":
            continue
        pattern = re.escape(route).replace(r"\*", ".*")
        pattern = re.sub(r"\\:\w+", r"[^/]+", pattern)
        if re.fullmatch(pattern, clean):
            return True
    return False


@pytest.fixture()
def routes() -> set[str]:
    return mini_app_paths()


def test_the_film_card_does_not_offer_to_book_that_film(routes):
    """The film is agreed with the administrator, never reserved in the app."""
    markup = bot_module.movie_keyboard(
        {"id": 7, "title": "Дюна", "trailer_id": "abc123"}
    )
    for path in keyboard_paths(markup):
        assert not re.match(r"^/booking/\d+", path), f"{path} books a specific film"


def test_every_bot_button_opens_a_screen_the_mini_app_serves(routes):
    markup = bot_module.movie_keyboard({"id": 7, "title": "Дюна", "trailer_id": ""})
    paths = keyboard_paths(markup) + keyboard_paths(bot_module.main_keyboard())
    assert paths, "the bot should open the mini app somewhere"
    for path in paths:
        assert matches_route(path, routes), f"the mini app has no route for {path}, only {sorted(routes)}"


def test_the_ticket_entry_is_the_generic_one(routes):
    paths = keyboard_paths(bot_module.main_keyboard())
    assert any(path.startswith("/tickets") for path in paths), (
        f"the bot must lead to the one ticket flow, saw {paths}"
    )
