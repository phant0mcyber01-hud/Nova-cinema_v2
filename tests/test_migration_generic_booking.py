"""Phase A migration: the generic inventory arrives without losing a booking.

The interesting part of 0018 is not the new tables -- it is the old rows.  A
cinema that has been taking movie-bound requests for months must come out of the
upgrade with every one of them intact, with a `party_size` that matches the
seats they hold, and must survive a rollback if the deployment goes wrong.
"""
from __future__ import annotations

import os
import pathlib
import sqlite3
import subprocess
import sys

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
PREVIOUS = "0017_booking_promo_code"
CURRENT = "0018_generic_capacity_booking"


def _alembic(*args: str, database_url: str) -> subprocess.CompletedProcess[str]:
    environment = {**os.environ, "DATABASE_URL": database_url, "AUTO_CREATE_SCHEMA": "false"}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
    )


@pytest.fixture()
def legacy_database(tmp_path: pathlib.Path):
    """A database at 0017 holding a movie, a user and two real bookings."""
    path = tmp_path / "legacy.db"
    url = f"sqlite+aiosqlite:///{path.as_posix()}"
    up = _alembic("upgrade", PREVIOUS, database_url=url)
    assert up.returncode == 0, up.stderr

    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO movies (id, title, genre, description, poster, trailer_id,"
            " duration, age, year, country, director, imdb, kinopoisk, cast_json, gallery_json)"
            " VALUES (1, 'Дюна', 'Фантастика', '', '', '', 166, 12, 2024, '', '', 8.6, 8.7,"
            " '[]', '[]')"
        )
        connection.execute(
            "INSERT INTO users (id, telegram_id, name, username, role)"
            " VALUES (1, 555, 'Иван', 'ivan', 'user')"
        )
        connection.execute(
            "INSERT INTO bookings (id, user_id, movie_id, session, show_date, seats, status,"
            " code, total, ticket_price, uuid, qr_token, created_at)"
            " VALUES (1, 1, 1, '19:00', '2026-08-27', '1-1,1-2,2-3', 'confirmed',"
            " '555', 90000, 30000, 'uuid-one', 'qr-one', '2026-08-20 10:00:00')"
        )
        connection.execute(
            "INSERT INTO bookings (id, user_id, movie_id, session, show_date, seats, status,"
            " code, total, ticket_price, uuid, qr_token, created_at)"
            " VALUES (2, 1, 1, '21:00', '2026-08-28', '3-1', 'cancelled',"
            " '555', 30000, 30000, 'uuid-two', 'qr-two', '2026-08-20 10:05:00')"
        )
        # An ephemeral hold: worthless after a deployment, and it must not be
        # what makes the upgrade fail.
        connection.execute(
            "INSERT INTO seat_holds (movie_id, show_date, session, seat, user_id, expires_at)"
            " VALUES (1, '2026-08-27', '19:00', '3-3', 1, '2026-08-27 12:00:00')"
        )
        connection.commit()
    return path, url


def _rows(path: pathlib.Path, query: str) -> list[tuple]:
    with sqlite3.connect(path) as connection:
        return list(connection.execute(query))


def _columns(path: pathlib.Path, table: str) -> dict[str, sqlite3.Row]:
    with sqlite3.connect(path) as connection:
        return {row[1]: row for row in connection.execute(f"PRAGMA table_info({table})")}


@pytest.mark.slow
def test_the_upgrade_keeps_every_legacy_booking(legacy_database):
    path, url = legacy_database
    up = _alembic("upgrade", CURRENT, database_url=url)
    assert up.returncode == 0, up.stderr

    rows = _rows(path, "SELECT id, movie_id, seats, status, total, uuid, qr_token FROM bookings ORDER BY id")
    assert rows == [
        (1, 1, "1-1,1-2,2-3", "confirmed", 90000, "uuid-one", "qr-one"),
        (2, 1, "3-1", "cancelled", 30000, "uuid-two", "qr-two"),
    ], "history must survive the upgrade untouched"


@pytest.mark.slow
def test_party_size_is_backfilled_from_the_seats_the_booking_holds(legacy_database):
    path, url = legacy_database
    assert _alembic("upgrade", CURRENT, database_url=url).returncode == 0

    assert _rows(path, "SELECT id, party_size FROM bookings ORDER BY id") == [(1, 3), (2, 1)]


@pytest.mark.slow
def test_movie_id_becomes_optional_and_seats_stay_compatible(legacy_database):
    path, url = legacy_database
    assert _alembic("upgrade", CURRENT, database_url=url).returncode == 0

    columns = _columns(path, "bookings")
    assert columns["movie_id"][3] == 0, "a request without a film must be storable"
    assert columns["seats"][3] == 1, "the legacy seat list stays as it was"

    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO bookings (id, user_id, movie_id, session, show_date, seats, party_size,"
            " status, code, total, ticket_price, uuid, qr_token, created_at)"
            " VALUES (3, 1, NULL, '18:00', '2026-08-29', '1,2', 2, 'pending',"
            " '555', 60000, 30000, 'uuid-three', 'qr-three', '2026-08-21 10:00:00')"
        )
        connection.commit()
    assert _rows(path, "SELECT movie_id FROM bookings WHERE id = 3") == [(None,)]


@pytest.mark.slow
def test_the_upgrade_brings_the_five_fixed_times(legacy_database):
    path, url = legacy_database
    assert _alembic("upgrade", CURRENT, database_url=url).returncode == 0

    rows = _rows(path, "SELECT start_time, is_active FROM slot_templates ORDER BY sort_order")
    assert [time for time, _ in rows] == ["12:00", "14:00", "16:00", "18:00", "20:00"]
    assert all(active for _, active in rows)
    assert "movie_id" not in _columns(path, "slot_templates")


@pytest.mark.slow
def test_ephemeral_holds_are_rebuilt_clean(legacy_database):
    path, url = legacy_database
    assert _alembic("upgrade", CURRENT, database_url=url).returncode == 0

    assert _rows(path, "SELECT COUNT(*) FROM seat_holds") == [(0,)]
    assert _rows(path, "SELECT COUNT(*) FROM capacity_holds") == [(0,)]
    # Scoped by the hall and the hour, never by the film.
    indexes = _rows(path, "PRAGMA index_list(capacity_holds)")
    unique = [name for _, name, is_unique, *_ in indexes if is_unique]
    assert unique, "the database itself must refuse the thirteenth place"
    with sqlite3.connect(path) as connection:
        keyed = {
            name: [row[2] for row in connection.execute(f"PRAGMA index_info({name})")]
            for name in unique
        }
    assert any(
        set(columns) == {"show_date", "start_time", "token"} for columns in keyed.values()
    ), f"the capacity key must be date+time+token, got {keyed}"


@pytest.mark.slow
def test_the_admin_contacts_land_on_the_settings_row(legacy_database):
    path, url = legacy_database
    # The settings row already exists at 0017; the new columns have to land on it
    # rather than only on a database created from scratch.
    assert _rows(path, "SELECT COUNT(*) FROM cinema_settings") == [(1,)]
    assert _alembic("upgrade", CURRENT, database_url=url).returncode == 0

    assert _rows(path, "SELECT admin_phone, admin_telegram FROM cinema_settings") == [
        ("91 326 20 65", "@Hhkcjoj")
    ]


@pytest.mark.slow
def test_the_rollback_keeps_the_history_too(legacy_database):
    path, url = legacy_database
    assert _alembic("upgrade", CURRENT, database_url=url).returncode == 0
    down = _alembic("downgrade", PREVIOUS, database_url=url)
    assert down.returncode == 0, f"the rollback path is broken:\n{down.stderr}"

    assert _rows(path, "SELECT id, movie_id, seats, uuid FROM bookings ORDER BY id") == [
        (1, 1, "1-1,1-2,2-3", "uuid-one"),
        (2, 1, "3-1", "uuid-two"),
    ]
    assert _rows(path, "SELECT name FROM sqlite_master WHERE name = 'capacity_holds'") == []

    again = _alembic("upgrade", CURRENT, database_url=url)
    assert again.returncode == 0, f"the schema cannot be rebuilt after a rollback:\n{again.stderr}"


@pytest.mark.slow
def test_a_rollback_does_not_delete_a_filmless_request(legacy_database):
    """A generic booking cannot become movie-bound again, but it must not vanish."""
    path, url = legacy_database
    assert _alembic("upgrade", CURRENT, database_url=url).returncode == 0
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO bookings (id, user_id, movie_id, session, show_date, seats, party_size,"
            " status, code, total, ticket_price, uuid, qr_token, created_at)"
            " VALUES (3, 1, NULL, '18:00', '2026-08-29', '1,2', 2, 'pending',"
            " '555', 60000, 30000, 'uuid-three', 'qr-three', '2026-08-21 10:00:00')"
        )
        connection.commit()

    down = _alembic("downgrade", PREVIOUS, database_url=url)
    assert down.returncode == 0, down.stderr
    assert _rows(path, "SELECT id, uuid FROM bookings ORDER BY id") == [
        (1, "uuid-one"),
        (2, "uuid-two"),
        (3, "uuid-three"),
    ], "a rollback may adopt a fallback film, but never drop the request"
