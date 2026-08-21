"""Share links for a movie card.

One place owns the payload format so the button that builds a link, the bot that
receives `/start`, and the Mini App that reads `start_param` cannot drift apart.
"""
from __future__ import annotations

import re

MOVIE_PAYLOAD = re.compile(r"movie_(\d{1,9})")


def movie_payload(movie_id: int) -> str:
    return f"movie_{movie_id}"


def movie_id_from_payload(payload: str | None) -> int | None:
    """Return the movie id, or None for a missing, foreign or malformed payload."""
    match = MOVIE_PAYLOAD.fullmatch((payload or "").strip())
    if match is None:
        return None
    movie_id = int(match.group(1))
    return movie_id or None


def share_link(bot_username: str | None, movie_id: int) -> str:
    """`startapp` opens the Mini App straight on the card; empty when unconfigured."""
    handle = (bot_username or "").strip().lstrip("@")
    if not handle:
        return ""
    return f"https://t.me/{handle}?startapp={movie_payload(movie_id)}"
