"""Configuration regressions fixed in stage 2."""
from __future__ import annotations

from backend.core import config


def test_empty_database_url_falls_back_instead_of_crashing(monkeypatch):
    """`DATABASE_URL=` in .env used to make create_async_engine raise at import."""
    monkeypatch.setenv("DATABASE_URL", "")
    assert config._clean(None, "fallback") == "fallback"
    assert config._clean("", "fallback") == "fallback"
    assert config._clean("   ", "fallback") == "fallback"
    assert config._clean("postgresql://x", "fallback") == "postgresql://x"


def test_cors_origins_drop_trailing_slash():
    """Browsers send Origin without a trailing slash, so the configured value is normalised."""
    assert config._origins("https://a.test/, https://b.test ,") == ["https://a.test", "https://b.test"]
    assert config.CORS_ORIGINS == ["https://example.test", "https://second.test"]


def test_admin_ids_ignore_junk():
    assert config._admin_ids("111, 222 ,abc,") == {111, 222}
    assert config._admin_ids("") == set()


def test_hall_seed_matches_the_real_auditorium():
    """Nova Cinema has one hall: 3 rows of 5 seats.

    These constants only seed the settings row -- after the first run the
    admin-managed database values are authoritative.
    """
    assert (config.DEFAULT_HALL_ROWS, config.DEFAULT_HALL_COLS) == (3, 5)
    assert config.DEFAULT_MAX_SEATS_PER_BOOKING <= config.DEFAULT_HALL_ROWS * config.DEFAULT_HALL_COLS


def test_booking_lifecycle_matches_the_spec():
    assert config.BOOKING_STATUSES == ("pending", "contacting", "confirmed", "cancelled", "watched")
    # Cancelling must free the seat; every other status keeps it.
    assert "cancelled" not in config.BLOCKING_STATUSES
    assert set(config.BLOCKING_STATUSES) | {"cancelled"} == set(config.BOOKING_STATUSES)
    assert config.QR_VALID_STATUSES == ("confirmed", "watched")
