"""Everything the administrator controls without touching code.

One `cinema_settings` row (id=1) holds the cinema profile, the ticket price and
the booking/hall parameters.  Bonuses, melodies and gallery images are separate
lists managed from the same admin panel.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.core import config
from backend.core.db import Base, utcnow


class CinemaSettings(Base):
    __tablename__ = "cinema_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)

    # Cinema profile
    name: Mapped[str] = mapped_column(String(160), default=config.DEFAULT_CINEMA_NAME)
    name_uz: Mapped[str] = mapped_column(String(160), default=config.DEFAULT_CINEMA_NAME)
    address: Mapped[str] = mapped_column(String(255), default=config.DEFAULT_ADDRESS)
    address_uz: Mapped[str] = mapped_column(String(255), default=config.DEFAULT_ADDRESS_UZ)
    phone: Mapped[str] = mapped_column(String(32), default=config.DEFAULT_PHONE)
    telegram_url: Mapped[str] = mapped_column(String(255), default=config.DEFAULT_TELEGRAM_URL)
    instagram_url: Mapped[str] = mapped_column(String(255), default=config.DEFAULT_INSTAGRAM_URL)
    #: Bot handle without @, used to build share deep links (t.me/<bot>?startapp=…).
    bot_username: Mapped[str] = mapped_column(String(64), default="")
    map_url: Mapped[str] = mapped_column(String(512), default="")
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    work_hours: Mapped[str] = mapped_column(String(120), default=config.DEFAULT_WORK_HOURS)
    work_hours_uz: Mapped[str] = mapped_column(String(120), default=config.DEFAULT_WORK_HOURS)
    about: Mapped[str] = mapped_column(Text, default="")
    about_uz: Mapped[str] = mapped_column(Text, default="")

    # Pricing
    base_ticket_price: Mapped[int] = mapped_column(Integer, default=config.DEFAULT_TICKET_PRICE)
    currency: Mapped[str] = mapped_column(String(8), default=config.DEFAULT_CURRENCY)

    # The single auditorium and the booking rules
    hall_rows: Mapped[int] = mapped_column(Integer, default=config.DEFAULT_HALL_ROWS)
    hall_cols: Mapped[int] = mapped_column(Integer, default=config.DEFAULT_HALL_COLS)
    max_seats_per_booking: Mapped[int] = mapped_column(Integer, default=config.DEFAULT_MAX_SEATS_PER_BOOKING)
    hold_minutes: Mapped[int] = mapped_column(Integer, default=config.DEFAULT_HOLD_MINUTES)
    booking_days_ahead: Mapped[int] = mapped_column(Integer, default=config.DEFAULT_BOOKING_DAYS_AHEAD)
    #: Offset from UTC in minutes; decides when a screening counts as finished.
    timezone_offset_minutes: Mapped[int] = mapped_column(
        Integer, default=config.DEFAULT_TIMEZONE_OFFSET_MINUTES
    )

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    @property
    def hall_seats(self) -> int:
        return self.hall_rows * self.hall_cols


class Bonus(Base):
    """Admin-authored promotions shown in the Mini App (spec 4.6)."""

    __tablename__ = "bonuses"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(160), default="")
    title_uz: Mapped[str] = mapped_column(String(160), default="")
    text: Mapped[str] = mapped_column(Text, default="")
    text_uz: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Melody(Base):
    """Uploaded audio, capped at MAX_MELODIES by the service layer (spec 4.7)."""

    __tablename__ = "melodies"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(160), default="")
    file_url: Mapped[str] = mapped_column(String(512))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GalleryImage(Base):
    """Interior / hall / bar photos for the About section (spec 16)."""

    __tablename__ = "gallery_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    image_url: Mapped[str] = mapped_column(String(512))
    caption: Mapped[str] = mapped_column(String(255), default="")
    caption_uz: Mapped[str] = mapped_column(String(255), default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
