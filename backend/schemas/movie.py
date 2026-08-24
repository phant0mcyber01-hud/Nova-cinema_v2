from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from backend.core.config import DATE_PATTERN

from backend.services.media import youtube_video_id


class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    text: str = Field(min_length=3, max_length=1000)


class MovieIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    genre: str = Field(min_length=1, max_length=120)
    description: str
    poster: str
    trailer_id: str
    duration: int = Field(ge=1)
    age: int = Field(ge=0, le=21)
    year: int = Field(ge=1888, le=2100)
    country: str
    director: str
    cast: list[str] = Field(default_factory=list)
    gallery: list[str] = Field(default_factory=list)
    imdb: float = Field(ge=0, le=10)
    kinopoisk: float = Field(ge=0, le=10)
    internal_rating: float | None = Field(default=None, ge=0, le=10)
    ticket_price: int | None = Field(default=None, ge=1)
    is_published: bool = True
    is_new: bool = False
    new_until: str = Field(default="", pattern=f"^$|{DATE_PATTERN[1:-1]}")
    is_hit: bool = False
    sort_order: int = 0

    @field_validator("trailer_id")
    @classmethod
    def normalize_trailer(cls, value: str) -> str:
        return youtube_video_id(value)


class MovieLookupIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class ReviewModerationIn(BaseModel):
    approved: bool
