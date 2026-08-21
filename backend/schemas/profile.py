from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

from backend.core.config import PHONE_PATTERN


class ProfileIn(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(default="", max_length=80)
    phone: str = Field(default="", max_length=32)

    @field_validator("first_name")
    @classmethod
    def validate_first_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("First name is required")
        return value

    @field_validator("last_name")
    @classmethod
    def normalize_last_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        value = value.strip()
        if not value:
            return ""
        if not re.fullmatch(PHONE_PATTERN, value):
            raise ValueError("Invalid phone number")
        normalized = "+" + "".join(character for character in value if character.isdigit())
        if not 8 <= len(normalized) <= 16:
            raise ValueError("Invalid phone number")
        return normalized
