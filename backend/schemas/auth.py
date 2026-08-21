from __future__ import annotations

from pydantic import BaseModel, Field


class TelegramAuthIn(BaseModel):
    init_data: str = Field(min_length=10)
