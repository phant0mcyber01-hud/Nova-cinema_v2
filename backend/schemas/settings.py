from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from backend.core.config import MAX_FAQ_ITEMS, MAX_HALL_COLS, MAX_HALL_ROWS, PHONE_PATTERN


class FaqItemIn(BaseModel):
    question_ru: str = Field(default="", max_length=300)
    answer_ru: str = Field(default="", max_length=2000)
    question_uz: str = Field(default="", max_length=300)
    answer_uz: str = Field(default="", max_length=2000)


class BasePriceIn(BaseModel):
    base_ticket_price: int = Field(ge=1, le=10_000_000)


class SettingsIn(BaseModel):
    """Everything on the admin settings form (spec 4.9 / 16)."""

    name: str = Field(min_length=1, max_length=160)
    name_uz: str = Field(default="", max_length=160)
    address: str = Field(default="", max_length=255)
    address_uz: str = Field(default="", max_length=255)
    phone: str = Field(default="", max_length=32)
    #: Whoever the viewer settles the film and the manual transfer with.
    admin_phone: str = Field(default="", max_length=32)
    admin_telegram: str = Field(default="", max_length=64, pattern=r"^$|^@?[A-Za-z0-9_]{4,63}$")
    telegram_url: str = Field(default="", max_length=255)
    instagram_url: str = Field(default="", max_length=255)
    bot_username: str = Field(default="", max_length=64, pattern=r"^$|^@?[A-Za-z0-9_]{4,63}$")
    map_url: str = Field(default="", max_length=512)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    work_hours: str = Field(default="", max_length=120)
    work_hours_uz: str = Field(default="", max_length=120)
    about: str = Field(default="", max_length=4000)
    about_uz: str = Field(default="", max_length=4000)
    important: str = Field(default="", max_length=2000)
    important_uz: str = Field(default="", max_length=2000)
    faq: list[FaqItemIn] = Field(default_factory=list, max_length=MAX_FAQ_ITEMS)

    base_ticket_price: int = Field(ge=1, le=10_000_000)
    currency: str = Field(default="UZS", min_length=1, max_length=8)

    hall_rows: int = Field(ge=1, le=MAX_HALL_ROWS)
    hall_cols: int = Field(ge=1, le=MAX_HALL_COLS)
    max_seats_per_booking: int = Field(ge=1, le=50)
    hold_minutes: int = Field(ge=1, le=180)
    booking_days_ahead: int = Field(ge=1, le=60)
    #: 0 switches automatic expiry off; the ceiling is a fortnight.
    pending_expire_hours: int = Field(default=24, ge=0, le=336)
    timezone_offset_minutes: int = Field(ge=-720, le=840)

    @field_validator("phone", "admin_phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        import re

        value = value.strip()
        if value and not re.fullmatch(PHONE_PATTERN, value):
            raise ValueError("Invalid phone number")
        return value

    @field_validator("telegram_url", "instagram_url", "map_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        value = value.strip()
        if value and not value.startswith(("http://", "https://")):
            raise ValueError("Link must start with http:// or https://")
        return value


class BonusIn(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    title_uz: str = Field(default="", max_length=160)
    text: str = Field(default="", max_length=4000)
    text_uz: str = Field(default="", max_length=4000)
    is_active: bool = True
    sort_order: int = 0


class MelodyIn(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    file_url: str = Field(min_length=1, max_length=512)
    sort_order: int = 0


class MelodyPatchIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    file_url: str | None = Field(default=None, min_length=1, max_length=512)
    sort_order: int | None = None


class GalleryImageIn(BaseModel):
    image_url: str = Field(min_length=1, max_length=512)
    caption: str = Field(default="", max_length=255)
    caption_uz: str = Field(default="", max_length=255)
    sort_order: int = 0
