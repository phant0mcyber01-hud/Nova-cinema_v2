"""Compatibility entrypoint.

The application itself lives in the `backend` package (stage 2 refactor).
This module keeps `uvicorn app:app`, the Dockerfile CMD and the VS Code
launch config working unchanged.
"""
from __future__ import annotations

from backend.core.config import DATABASE_URL
from backend.core.db import Base, SessionLocal, engine, get_db
from backend.main import app
from backend.models import (
    AdminNotification,
    Booking,
    Bonus,
    CinemaSettings,
    Favorite,
    GalleryImage,
    Melody,
    Movie,
    Review,
    SeatHold,
    Show,
    User,
    UserNotification,
)
from backend.services.catalog import serialize_movie

__all__ = [
    "AdminNotification",
    "Base",
    "Bonus",
    "Booking",
    "CinemaSettings",
    "DATABASE_URL",
    "Favorite",
    "GalleryImage",
    "Melody",
    "Movie",
    "Review",
    "SeatHold",
    "SessionLocal",
    "Show",
    "User",
    "UserNotification",
    "app",
    "engine",
    "get_db",
    "serialize_movie",
]
