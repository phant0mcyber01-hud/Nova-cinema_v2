"""Seat geometry for the single Nova Cinema auditorium.

The grid comes from the admin-managed settings row, so changing the hall never
requires a code change.  Seats are addressed as "<row>-<column>", both 1-based.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import CinemaSettings
from backend.services.settings import get_settings


def parse_seat(seat: str) -> tuple[int, int] | None:
    try:
        row, column = (int(value) for value in seat.split("-", 1))
    except ValueError:
        return None
    return row, column


def valid_seat(seat: str, rows: int, cols: int) -> bool:
    parsed = parse_seat(seat)
    if parsed is None:
        return False
    row, column = parsed
    return 1 <= row <= rows and 1 <= column <= cols


async def hall_layout(session: AsyncSession) -> CinemaSettings:
    """The settings row doubles as the hall description."""
    return await get_settings(session)
