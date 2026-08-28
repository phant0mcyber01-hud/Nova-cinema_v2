"""Booking requests and the admin notifications they raise."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.db import Base, utcnow


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Optimistic locking works on SQLite too, unlike SELECT FOR UPDATE.
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    #: Nullable since the generic booking flow: the mini app reserves places in
    #: the hall, and which film is played is agreed with the administrator
    #: outside the app. Kept for the legacy movie-bound history and for the
    #: film an administrator may attach to a request after the fact.
    movie_id: Mapped[int | None] = mapped_column(
        ForeignKey("movies.id"), nullable=True, index=True
    )
    session: Mapped[str] = mapped_column(String(30))
    show_date: Mapped[str] = mapped_column(String(10), default="", index=True)
    #: Legacy bookings hold real seat labels ("2-3"). Generic ones hold the
    #: internal capacity tokens ("1,2,3"), which are never shown to a viewer.
    seats: Mapped[str] = mapped_column(String(255))
    #: How many people the request is for. Authoritative for capacity; on
    #: legacy rows it was backfilled from the length of the seat list.
    party_size: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    code: Mapped[str] = mapped_column(String(32), default="")
    total: Mapped[int] = mapped_column(Integer, default=0)
    #: Price per seat frozen at request time, so later price changes do not
    #: rewrite the history of existing bookings.
    ticket_price: Mapped[int] = mapped_column(Integer, default=0)
    first_name: Mapped[str] = mapped_column(String(80), default="")
    last_name: Mapped[str] = mapped_column(String(80), default="")
    phone: Mapped[str] = mapped_column(String(32), default="")
    telegram_username: Mapped[str] = mapped_column(String(80), default="")
    comment: Mapped[str] = mapped_column(Text, default="")
    #: Typed by the viewer, honoured by the admin during the callback — the
    #: server never computes a discount from it.
    promo_code: Mapped[str] = mapped_column(String(64), default="")
    proposed_session: Mapped[str] = mapped_column(String(30), default="")
    admin_note: Mapped[str] = mapped_column(Text, default="")
    uuid: Mapped[str] = mapped_column(String(36), default=lambda: str(uuid.uuid4()), unique=True, index=True)
    qr_token: Mapped[str] = mapped_column(String(64), default=lambda: uuid.uuid4().hex, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    #: Set when a booking becomes terminal (`cancelled` or `watched`).
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: Viewer-side cleanup hides terminal history but preserves the admin audit row.
    viewer_hidden_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    __mapper_args__ = {"version_id_col": version}


class AdminNotification(Base):
    __tablename__ = "admin_notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id"), index=True)
    message: Mapped[str] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
