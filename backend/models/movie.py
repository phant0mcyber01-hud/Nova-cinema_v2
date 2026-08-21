"""Catalog: movies and their reviews."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.db import Base, utcnow


class Movie(Base):
    __tablename__ = "movies"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    genre: Mapped[str] = mapped_column(String(120), index=True)
    description: Mapped[str] = mapped_column(Text)
    title_ru: Mapped[str] = mapped_column(String(255), default="")
    title_uz: Mapped[str] = mapped_column(String(255), default="")
    genre_ru: Mapped[str] = mapped_column(String(120), default="")
    genre_uz: Mapped[str] = mapped_column(String(120), default="")
    description_ru: Mapped[str] = mapped_column(Text, default="")
    description_uz: Mapped[str] = mapped_column(Text, default="")
    poster: Mapped[str] = mapped_column(String(1024))
    trailer_id: Mapped[str] = mapped_column(String(64))
    duration: Mapped[int] = mapped_column(Integer)
    age: Mapped[int] = mapped_column(Integer)
    year: Mapped[int] = mapped_column(Integer)
    country: Mapped[str] = mapped_column(String(255))
    director: Mapped[str] = mapped_column(String(255))
    cast_json: Mapped[str] = mapped_column(Text, default="[]")
    country_ru: Mapped[str] = mapped_column(String(255), default="")
    country_uz: Mapped[str] = mapped_column(String(255), default="")
    director_ru: Mapped[str] = mapped_column(String(255), default="")
    director_uz: Mapped[str] = mapped_column(String(255), default="")
    cast_json_ru: Mapped[str] = mapped_column(Text, default="[]")
    cast_json_uz: Mapped[str] = mapped_column(Text, default="[]")
    gallery_json: Mapped[str] = mapped_column(Text, default="[]")
    imdb: Mapped[float] = mapped_column(Float)
    kinopoisk: Mapped[float] = mapped_column(Float)
    internal_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_published: Mapped[bool] = mapped_column(default=True, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, index=True)
    ticket_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: Marked as a new release by the admin; `new_until` optionally expires it.
    is_new: Mapped[bool] = mapped_column(default=False, index=True)
    new_until: Mapped[str] = mapped_column(String(10), default="")

    reviews: Mapped[list["Review"]] = relationship(back_populates="movie", cascade="all, delete-orphan")


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    rating: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    approved: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    movie: Mapped[Movie] = relationship(back_populates="reviews")
