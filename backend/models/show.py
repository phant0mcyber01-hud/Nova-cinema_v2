"""Screenings and short-lived seat holds.

`shows` is the single source of truth for the schedule.  It replaces the old
split between `Movie.sessions_json` (base times, no dates) and `session_prices`
(per-date overrides), which let any well-formed HH:MM be booked.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.db import Base, utcnow


class Show(Base):
    __tablename__ = "shows"
    __table_args__ = (UniqueConstraint("movie_id", "show_date", "start_time", name="uq_show_slot"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id"), index=True)
    show_date: Mapped[str] = mapped_column(String(10), index=True)
    start_time: Mapped[str] = mapped_column(String(5), index=True)
    #: Overrides the movie price and the global base price when set.
    ticket_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SeatHold(Base):
    __tablename__ = "seat_holds"
    __table_args__ = (UniqueConstraint("movie_id", "show_date", "session", "seat", name="uq_seat_hold"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id"), index=True)
    show_date: Mapped[str] = mapped_column(String(10), index=True)
    session: Mapped[str] = mapped_column(String(30), index=True)
    seat: Mapped[str] = mapped_column(String(10), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
