"""Letting go of requests the administrator never answered.

Payment is manual, so a request waits in `pending` until somebody phones the
viewer back. Nothing released those places, which meant one forgotten request
kept part of the hall out of circulation permanently -- and because a full slot
disappears from the booking screen, a day could quietly stop selling.

The rule is deliberately narrow:

* only `pending` expires. `contacting` means the administrator is already
  talking to that person, and confirming or declining is their decision, not a
  timer's;
* the request is cancelled, never deleted. The code, the uuid, the QR token and
  the contacts stay exactly where they were;
* the viewer is told why, because a booking that vanishes without a word is
  worse than the bug this fixes.
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.db import utcnow
from backend.models import Booking
from backend.services.settings import get_settings

__all__ = ["EXPIRY_NOTE", "expire_stale_requests"]

#: What the viewer reads on the cancelled request.
EXPIRY_NOTE = (
    "Заявка отменена автоматически: администратор не успел её подтвердить. "
    "Свободные места вернулись в зал — оформите новую заявку или свяжитесь с администратором."
)


async def expire_stale_requests(session: AsyncSession) -> int:
    """Cancel `pending` requests older than the admin's window.

    Returns how many were cancelled. The caller commits: this runs inside the
    same transaction as the availability read that triggered it, so a request
    can never be counted as holding places and expired at the same time.
    """
    settings = await get_settings(session)
    hours = settings.pending_expire_hours
    if hours <= 0:
        # 0 switches the whole thing off: some cinemas would rather chase every
        # request by hand than have the app cancel one behind their back.
        return 0

    cutoff = utcnow() - timedelta(hours=hours)
    stale = list(
        await session.scalars(
            select(Booking).where(Booking.status == "pending", Booking.created_at < cutoff)
        )
    )
    for booking in stale:
        booking.status = "cancelled"
        # Only fill the note if the administrator has not written one: their
        # own words outrank this sentence.
        if not booking.admin_note:
            booking.admin_note = EXPIRY_NOTE
    return len(stale)
