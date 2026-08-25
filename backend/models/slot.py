"""The generic booking inventory: fixed times, and the capacity tokens they hold.

Neither table mentions a film.  Nova Cinema books one hall for a date and one
of the administrator's fixed times; which film is played in that slot is agreed
between the viewer and the administrator afterwards and is deliberately not part
of the reservation.  `shows` stays behind for the legacy movie-bound schedule.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.db import Base, utcnow


class SlotTemplate(Base):
    """One admin-managed time of day, offered on every date in the window."""

    __tablename__ = "slot_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    start_time: Mapped[str] = mapped_column(String(5), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, index=True)
    #: Reserved for a later per-slot price.  The current formula is
    #: `base_ticket_price * party_size` and deliberately ignores this column.
    ticket_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CapacityHold(Base):
    """A short-lived claim on one of the hall's virtual capacity tokens.

    The token is an internal number, `1..hall_seats`.  It is not a seat: the
    viewer never picks one and is never shown one.  It exists so the database
    itself — not a check in Python — refuses to sell the thirteenth place, and
    the unique key is scoped by date and time only, so the same physical hall
    cannot be sold twice for two different films at the same hour.
    """

    __tablename__ = "capacity_holds"
    __table_args__ = (
        UniqueConstraint("show_date", "start_time", "token", name="uq_capacity_hold"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    show_date: Mapped[str] = mapped_column(String(10), index=True)
    start_time: Mapped[str] = mapped_column(String(5), index=True)
    token: Mapped[int] = mapped_column(Integer)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
