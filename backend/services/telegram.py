"""Outbound Telegram messages.  Failures are non-fatal for the calling request.

Messages go out over the raw Bot API with httpx rather than through the aiogram
`Bot` object in bot.py: the project's dependency direction is bot.py -> backend,
so importing the bot here would close that into a cycle.  The token and the
admin chat ids come from `backend.core.config`, which is the single place the
environment is parsed -- bot.py reads the very same values from there.
"""
from __future__ import annotations

import logging

import httpx

from backend.core import config
from backend.models import Booking, UserNotification

logger = logging.getLogger("nova-cinema.telegram")

TELEGRAM_API_BASE = "https://api.telegram.org"

#: Test seam.  The suite installs an `httpx.MockTransport` here so no test ever
#: reaches api.telegram.org.  `None` is the httpx default, so production traffic
#: is untouched.
transport: httpx.AsyncBaseTransport | None = None


async def send_telegram_message(telegram_id: int, message: str) -> None:
    """Deliver one message, swallowing every failure.

    A booking must never be lost because Telegram was unreachable, the token was
    rotated, or the recipient never pressed Start -- a bot cannot open a chat the
    user has not initiated, and that returns 403 rather than raising here.
    """
    token = config.bot_token()
    if not token:
        logger.warning("BOT_TOKEN is empty: skipping Telegram message to %s", telegram_id)
        return
    try:
        async with httpx.AsyncClient(timeout=8, transport=transport) as client:
            response = await client.post(
                f"{TELEGRAM_API_BASE}/bot{token}/sendMessage",
                json={"chat_id": telegram_id, "text": message},
            )
        if response.status_code != 200:
            # 403 here almost always means the admin has never started a chat
            # with the bot.  Nothing to retry, but it must be visible in the log.
            logger.warning(
                "Telegram refused a message to %s: HTTP %s %s",
                telegram_id, response.status_code, response.text[:200],
            )
    except Exception:
        # Deliberately broad: this is a best-effort side channel, and no failure
        # mode of it may propagate into the request that triggered it.
        logger.exception("Could not send a Telegram message to %s", telegram_id)


async def notify_admins(message: str) -> None:
    """Push a live copy of an admin notification into the admins' Telegram chats.

    The `AdminNotification` row in the database stays the record of truth for the
    admin panel; this is the real-time nudge on top of it.  Called after the
    transaction has committed, so it cannot roll anything back.
    """
    admin_ids = config.ADMIN_TELEGRAM_IDS
    if not admin_ids:
        logger.warning("ADMIN_TELEGRAM_IDS is empty: nobody to notify about %r", message[:80])
        return
    for admin_id in sorted(admin_ids):
        await send_telegram_message(admin_id, message)


def new_booking_admin_message(booking: Booking, movie_title: str) -> str:
    """The Russian text an admin receives when a viewer files a booking.

    Deliberately richer than the panel's one-line notification: the admin should
    be able to act on the request without opening the Mini App first.
    """
    seats = ", ".join(seat for seat in booking.seats.split(",") if seat)
    name = " ".join(part for part in (booking.first_name, booking.last_name) if part) or "Без имени"
    lines = [
        "Новая заявка на бронирование",
        f"Фильм: {movie_title}",
        f"Сеанс: {booking.show_date} {booking.session}",
        f"Места: {seats}",
        f"Сумма: {booking.total}",
        f"Клиент: {name}",
        f"Телефон: {booking.phone}",
    ]
    if booking.telegram_username:
        lines.append(f"Telegram: @{booking.telegram_username}")
    if booking.comment:
        lines.append(f"Комментарий: {booking.comment}")
    lines.append(f"Заявка #{booking.id}")
    return "\n".join(lines)


def user_booking_notification(booking: Booking, title: str, message: str) -> UserNotification:
    return UserNotification(user_id=booking.user_id, type="booking_status", title=title, message=message)
