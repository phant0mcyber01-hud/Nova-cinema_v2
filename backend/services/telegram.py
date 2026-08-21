"""Outbound Telegram messages.  Failures are non-fatal for the calling request."""
from __future__ import annotations

import httpx

from backend.core import config
from backend.models import Booking, UserNotification


async def send_telegram_message(telegram_id: int, message: str) -> None:
    token = config.bot_token()
    if not token:
        return
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": telegram_id, "text": message},
            )
    except httpx.HTTPError:
        return


def user_booking_notification(booking: Booking, title: str, message: str) -> UserNotification:
    return UserNotification(user_id=booking.user_id, type="booking_status", title=title, message=message)
