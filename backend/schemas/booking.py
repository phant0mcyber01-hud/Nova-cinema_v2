from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

from backend.core.config import (
    BOOKING_STATUS_PATTERN,
    DATE_PATTERN,
    PHONE_PATTERN,
    TIME_PATTERN,
    USERNAME_PATTERN,
)


class HoldIn(BaseModel):
    movie_id: int
    show_date: str = Field(pattern=DATE_PATTERN)
    session: str = Field(pattern=TIME_PATTERN)
    # The real ceiling is the admin-configured max_seats_per_booking; this
    # bound only stops an absurd payload before it reaches the database.
    seats: list[str] = Field(min_length=1, max_length=50)


class BookingConfirmIn(HoldIn):
    first_name: str = Field(min_length=2, max_length=80)
    last_name: str = Field(min_length=2, max_length=80)
    phone: str = Field(pattern=f"^{PHONE_PATTERN}$")
    telegram_username: str = Field(default="", max_length=80, pattern=USERNAME_PATTERN)
    comment: str = Field(default="", max_length=1000)
    promo_code: str = Field(default="", max_length=64)


class BookingStatusIn(BaseModel):
    status: str = Field(pattern=BOOKING_STATUS_PATTERN)


class BookingDecisionIn(BaseModel):
    # "contact" moves the request to `contacting` while the admin calls the client.
    action: str = Field(pattern=r"^(contact|confirm|decline|propose)$")
    reason: str = Field(default="", max_length=500)
    proposed_session: str = Field(default="", max_length=30)

    @field_validator("proposed_session")
    @classmethod
    def validate_proposed_session(cls, value: str) -> str:
        value = value.strip()
        if value and not re.fullmatch(TIME_PATTERN, value):
            raise ValueError("Invalid proposed time")
        return value


class BookingProposalIn(BaseModel):
    action: str = Field(pattern=r"^(accept|decline)$")
