"""Single place where environment configuration is read and normalised."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Docker supplies its own environment.  For a direct local `uvicorn app:app`
# launch, load this project's .env before reading any configuration values.
# `override=False` deliberately keeps Docker/Windows environment variables authoritative.
# `utf-8-sig` снимает BOM: Блокнот и PowerShell сохраняют файл с ним, а он
# прилипает к первому ключу — BOT_TOKEN читается как "﻿BOT_TOKEN" и
# выглядит как незаполненный.
load_dotenv(PROJECT_ROOT / ".env", override=False, encoding="utf-8-sig")


def _clean(value: str | None, fallback: str = "") -> str:
    """Treat an empty or whitespace-only variable the same as an unset one.

    `DATABASE_URL=` in .env makes os.getenv return "" rather than the default,
    which used to crash create_async_engine at import time.
    """
    return (value or "").strip() or fallback


def _origins(raw: str) -> list[str]:
    """Browsers send Origin without a trailing slash, so normalise the configured list."""
    return [item.strip().rstrip("/") for item in raw.split(",") if item.strip()]


def _admin_ids(raw: str) -> set[int]:
    return {int(item.strip()) for item in raw.split(",") if item.strip().isdigit()}


DATABASE_URL = _clean(os.getenv("DATABASE_URL"), "sqlite+aiosqlite:///./nova-dev.db")
JWT_SECRET = _clean(os.getenv("JWT_SECRET"))
JWT_ALGORITHM = "HS256"
WEBAPP_URL = _clean(os.getenv("WEBAPP_URL")).rstrip("/")
UPLOAD_DIR = Path(_clean(os.getenv("UPLOAD_DIR"), "uploads"))
TELEGRAM_AUTH_MAX_AGE_SECONDS = int(_clean(os.getenv("TELEGRAM_AUTH_MAX_AGE_SECONDS"), "86400"))
ADMIN_TELEGRAM_IDS = _admin_ids(os.getenv("ADMIN_TELEGRAM_IDS", ""))
CORS_ORIGINS = _origins(_clean(os.getenv("CORS_ORIGINS"), "http://localhost:5173"))
AUTO_CREATE_SCHEMA = _clean(os.getenv("AUTO_CREATE_SCHEMA"), "false").lower() == "true"

TMDB_API_KEY = _clean(os.getenv("TMDB_API_KEY"))
OMDB_API_KEY = _clean(os.getenv("OMDB_API_KEY"))
TRANSLATION_API_URL = _clean(os.getenv("TRANSLATION_API_URL"), "https://libretranslate.com/translate")
TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_URL = "https://image.tmdb.org/t/p"
OMDB_BASE_URL = "https://www.omdbapi.com/"

TIME_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"
DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
PHONE_PATTERN = r"\+?[0-9\s()\-]{7,32}"
USERNAME_PATTERN = r"^$|^@?[A-Za-z0-9_]{5,32}$"

# Seed values for the admin-managed settings row.  After the first run the
# database is authoritative -- nothing here is read at request time.
DEFAULT_CINEMA_NAME = "Nova Cinema"
DEFAULT_ADDRESS = "Юксалиш 97А"
DEFAULT_ADDRESS_UZ = "Yuksalish 97A"
DEFAULT_PHONE = "+998 91 326 20 65"
DEFAULT_TELEGRAM_URL = "https://t.me/novasinema"
DEFAULT_INSTAGRAM_URL = "https://www.instagram.com/nova_cinema__"
DEFAULT_MAP_URL = "https://yandex.go.link/discovery?action=card&oid=97603506332&adj_campaign=Share-from-the-app"
DEFAULT_WORK_HOURS = "10:00 - 23:00"
#: Whoever the viewer talks to about the film and the transfer. Separate from
#: the cinema switchboard and the public channel above: a request is settled
#: in a private conversation, not on the channel.
DEFAULT_ADMIN_PHONE = "91 326 20 65"
DEFAULT_ADMIN_TELEGRAM = "@Hhkcjoj"
#: A long list stops being an FAQ and starts being a wall of text nobody reads.
MAX_FAQ_ITEMS = 20
DEFAULT_CURRENCY = "UZS"

# Nova Cinema has exactly one auditorium: 3 rows of 4 seats, 12 in total.
# It is the whole booking inventory -- a slot is a date plus a time, and the
# film shown in it is never part of the reservation.
DEFAULT_HALL_ROWS = 3
DEFAULT_HALL_COLS = 4
DEFAULT_TICKET_PRICE = 30000
DEFAULT_MAX_SEATS_PER_BOOKING = 4
DEFAULT_HOLD_MINUTES = 10
#: Today plus 7 more days = 8 selectable dates. The client's own example:
#: today is Wed 25 Aug, the furthest bookable day is 1 Sep -- 8 calendar dates,
#: not 7. This is a rolling window: nothing caches it or resets it on a timer,
#: every request just reads the cinema's current date (see booking_window()).
DEFAULT_BOOKING_DAYS_AHEAD = 8
#: How long a request may wait for the administrator before it is cancelled and
#: its places go back to the hall. 0 switches the timer off entirely.
DEFAULT_PENDING_EXPIRE_HOURS = 24
#: The cinema's clock. The server runs in UTC; Uzbekistan is UTC+5 with no
#: daylight saving, so a fixed offset is exact. Minutes, to allow half-hour zones.
DEFAULT_TIMEZONE_OFFSET_MINUTES = 300
#: The fixed times the cinema opens for booking. Admin-managed from the first
#: run onwards -- these only seed `slot_templates`, and none of them belongs
#: to a film.
DEFAULT_SLOT_TIMES = ("12:00", "14:00", "16:00", "18:00", "20:00")

# Hard ceilings the admin cannot exceed, so a typo cannot break the hall grid.
MAX_HALL_ROWS = 26
MAX_HALL_COLS = 20
MAX_MELODIES = 3

UPLOAD_MAX_BYTES = 5_000_000
AUDIO_MAX_BYTES = 50_000_000
AUDIO_CHUNK_BYTES = 1_000_000
AUDIO_TRANSCODE_THRESHOLD_BYTES = 10_000_000

# Booking lifecycle (stage 12 of the spec).
BOOKING_STATUSES = ("pending", "contacting", "confirmed", "cancelled", "watched")
#: The seat is taken but the admin has not confirmed it yet.
AWAITING_STATUSES = ("pending", "contacting")
#: The seat is finally the viewer's.
CONFIRMED_STATUSES = ("confirmed", "watched")
#: Statuses that keep a seat occupied.  "cancelled" releases it.
BLOCKING_STATUSES = AWAITING_STATUSES + CONFIRMED_STATUSES
#: Statuses whose ticket QR is valid at the door.
QR_VALID_STATUSES = ("confirmed", "watched")
BOOKING_STATUS_PATTERN = "^(" + "|".join(BOOKING_STATUSES) + ")$"


def bot_token() -> str:
    """Read at call time so a late environment change is picked up, and strip
    the quotes a .env editor sometimes leaves behind."""
    return _clean(os.getenv("BOT_TOKEN")).strip('"')
