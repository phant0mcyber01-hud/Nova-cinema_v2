"""Configuration warnings raised at startup.

Deployment mistakes here are silent and expensive: a stale CORS origin only
shows up as an unexplained blank Mini App, and a short JWT secret shows up
never. Nothing raises — a warning must not stop the cinema from selling
tickets — but the log says plainly what is wrong.
"""
from __future__ import annotations

import logging

from backend.core import config

logger = logging.getLogger("nova-cinema")

#: Hosts that hand out a new address on every restart.
EPHEMERAL_HOSTS = ("trycloudflare.com", "ngrok.io", "ngrok-free.app", "loca.lt", "serveo.net")
MIN_SECRET_LENGTH = 32


def configuration_warnings() -> list[str]:
    """Everything worth telling the operator about, in plain words."""
    warnings: list[str] = []

    if not config.JWT_SECRET:
        warnings.append("JWT_SECRET is empty: authentication cannot work.")
    elif len(config.JWT_SECRET) < MIN_SECRET_LENGTH:
        warnings.append(
            f"JWT_SECRET is shorter than {MIN_SECRET_LENGTH} characters and is easier to guess."
        )

    if not config.bot_token():
        warnings.append("BOT_TOKEN is not set: Telegram sign-in and notifications are disabled.")

    if not config.ADMIN_TELEGRAM_IDS:
        warnings.append("ADMIN_TELEGRAM_IDS is empty: nobody can reach the admin panel.")

    for origin in config.CORS_ORIGINS:
        if any(host in origin for host in EPHEMERAL_HOSTS):
            warnings.append(
                f"CORS origin {origin} is a temporary tunnel: it will stop matching after a restart."
            )
    if not config.CORS_ORIGINS:
        warnings.append("CORS_ORIGINS is empty: the Mini App will be blocked by the browser.")

    if config.DATABASE_URL.startswith("sqlite"):
        warnings.append("DATABASE_URL points at SQLite — fine for development, not for production.")

    return warnings


def log_configuration_warnings() -> None:
    for warning in configuration_warnings():
        logger.warning("configuration: %s", warning)
