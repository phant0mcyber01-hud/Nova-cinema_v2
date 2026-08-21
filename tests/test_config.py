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


def test_bot_has_no_hardcoded_cinema_contacts():
    """The bot must read the contact block from settings, like the Mini App.

    Regression guard: the About section kept literal contacts long after the
    settings row existed, so the admin could not change what the bot showed.
    """
    import pathlib

    source = pathlib.Path(__file__).resolve().parents[1] / "bot.py"
    text = source.read_text(encoding="utf-8")
    for literal in ("Юксалиш", "+998 91 326", "t.me/novasinema", "instagram.com/nova_cinema__"):
        assert literal not in text, f"bot.py still hardcodes {literal!r}"
    assert "fetch_settings" in text, "bot.py should read the admin-managed settings row"


def test_profile_screen_uses_the_current_booking_lifecycle():
    """Regression: the profile filter kept the pre-stage-3 statuses."""
    import pathlib

    source = pathlib.Path(__file__).resolve().parents[1] / "frontend/src/pages/profile/Profile.tsx"
    text = source.read_text(encoding="utf-8")
    for status in config.BOOKING_STATUSES:
        assert f"'{status}'" in text, f"profile screen does not know status {status}"
    assert "'completed'" not in text, "profile screen still references the removed status"


# --- stage 20: the template a new deployment starts from ---------------------

import pathlib  # noqa: E402  -- kept next to the checks that use it
import re  # noqa: E402

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_env_example_documents_every_variable_the_app_reads():
    """README tells the operator to copy this file; it has to be complete."""
    template = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")
    source = (PROJECT_ROOT / "backend/core/config.py").read_text(encoding="utf-8")
    for name in sorted(set(re.findall(r'os\.getenv\("([A-Z_]+)"', source))):
        assert re.search(rf"^{name}=", template, re.M), f".env.example is missing {name}"


def test_env_example_carries_no_real_secrets():
    for line in (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        if line.startswith(("BOT_TOKEN=", "JWT_SECRET=", "POSTGRES_PASSWORD=", "TMDB_API_KEY=", "OMDB_API_KEY=")):
            assert line.split("=", 1)[1] == "", f"{line.split('=')[0]} must ship empty"


def test_the_bot_reads_the_environment_through_config():
    """One parser for the environment, or the two drift apart."""
    source = (PROJECT_ROOT / "bot.py").read_text(encoding="utf-8")
    assert "os.getenv" not in source, "bot.py must take its settings from backend.core.config"
    assert "config.bot_token()" in source
