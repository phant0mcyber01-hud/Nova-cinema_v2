"""Access to the single admin-managed settings row.

Nothing in the request path reads environment variables for cinema data: the
database row is authoritative, and `config.DEFAULT_*` only seeds it once.
"""
from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.db import SessionLocal
from backend.models import CinemaSettings
from backend.services.i18n import normalize_language

SETTINGS_ID = 1


async def get_settings(session: AsyncSession) -> CinemaSettings:
    """Return the settings row, creating it with seed defaults on first use.

    Nearly every endpoint calls this, so the first-run insert must survive
    concurrency: two requests against a fresh database would both see no row,
    both insert id=1, and one would die on the primary key.
    """
    settings = await session.get(CinemaSettings, SETTINGS_ID)
    if settings is not None:
        return settings

    # Create it in an independent session: if a parallel request wins the race,
    # the primary key blows up there and the caller's transaction stays clean.
    async with SessionLocal() as creator:
        creator.add(CinemaSettings(id=SETTINGS_ID))
        try:
            await creator.commit()
        except IntegrityError:
            await creator.rollback()
    return await session.get(CinemaSettings, SETTINGS_ID)


def serialize_settings(settings: CinemaSettings, language: str = "ru") -> dict[str, object]:
    """Public payload consumed by the Mini App and the bot."""
    uz = normalize_language(language) == "uz"
    return {
        "name": (settings.name_uz or settings.name) if uz else settings.name,
        "address": (settings.address_uz or settings.address) if uz else settings.address,
        "phone": settings.phone,
        "telegram_url": settings.telegram_url,
        "instagram_url": settings.instagram_url,
        "bot_username": settings.bot_username.lstrip("@"),
        "map_url": settings.map_url,
        "latitude": settings.latitude,
        "longitude": settings.longitude,
        "work_hours": (settings.work_hours_uz or settings.work_hours) if uz else settings.work_hours,
        "about": (settings.about_uz or settings.about) if uz else settings.about,
        "base_ticket_price": settings.base_ticket_price,
        "currency": settings.currency,
        "hall_rows": settings.hall_rows,
        "hall_cols": settings.hall_cols,
        "hall_seats": settings.hall_seats,
        "max_seats_per_booking": settings.max_seats_per_booking,
        "booking_days_ahead": settings.booking_days_ahead,
    }


def serialize_settings_admin(settings: CinemaSettings) -> dict[str, object]:
    """Full row for the admin form: both languages, plus the booking parameters."""
    return {
        "name": settings.name,
        "name_uz": settings.name_uz,
        "address": settings.address,
        "address_uz": settings.address_uz,
        "phone": settings.phone,
        "telegram_url": settings.telegram_url,
        "instagram_url": settings.instagram_url,
        "bot_username": settings.bot_username,
        "map_url": settings.map_url,
        "latitude": settings.latitude,
        "longitude": settings.longitude,
        "work_hours": settings.work_hours,
        "work_hours_uz": settings.work_hours_uz,
        "about": settings.about,
        "about_uz": settings.about_uz,
        "base_ticket_price": settings.base_ticket_price,
        "currency": settings.currency,
        "hall_rows": settings.hall_rows,
        "hall_cols": settings.hall_cols,
        "hall_seats": settings.hall_seats,
        "max_seats_per_booking": settings.max_seats_per_booking,
        "hold_minutes": settings.hold_minutes,
        "booking_days_ahead": settings.booking_days_ahead,
        "updated_at": settings.updated_at,
    }
