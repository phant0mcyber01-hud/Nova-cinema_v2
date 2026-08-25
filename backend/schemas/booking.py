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


class CapacityHoldIn(BaseModel):
    """The whole generic booking selection: a date, a fixed time, how many people.

    No `movie_id` and no seat list. The film is agreed with the administrator
    afterwards, and the hall is filled automatically.
    """

    date: str = Field(pattern=DATE_PATTERN)
    time: str = Field(pattern=TIME_PATTERN)
    # The real ceiling is the hall; this only stops an absurd payload before it
    # reaches the database.
    party_size: int = Field(ge=1, le=50)


class BookingRequestIn(CapacityHoldIn):
    """A request the administrator will phone back about.

    Deliberately carries no price: the total is `base_ticket_price * party_size`
    and is computed on the server, so a client cannot name its own.
    """

    first_name: str = Field(min_length=2, max_length=80)
    last_name: str = Field(min_length=2, max_length=80)
    phone: str = Field(pattern=f"^{PHONE_PATTERN}$")
    telegram_username: str = Field(default="", max_length=80, pattern=USERNAME_PATTERN)
    comment: str = Field(default="", max_length=1000)
    promo_code: str = Field(default="", max_length=64)


class SlotTemplateIn(BaseModel):
    """One admin-managed time of day. No film is involved."""

    start_time: str = Field(pattern=TIME_PATTERN)
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0, le=1000)


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
