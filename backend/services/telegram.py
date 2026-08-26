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


async def send_telegram_message(telegram_id: int, message: str, *, reply_markup: dict[str, object] | None = None) -> None:
    """Deliver one message, swallowing every failure.

    A booking must never be lost because Telegram was unreachable, the token was
    rotated, or the recipient never pressed Start -- a bot cannot open a chat the
    user has not initiated, and that returns 403 rather than raising here.

    `reply_markup` attaches an inline keyboard (see `admin_action_keyboard`)
    when the caller wants the message to double as an action card.
    """
    token = config.bot_token()
    if not token:
        logger.warning("BOT_TOKEN is empty: skipping Telegram message to %s", telegram_id)
        return
    payload: dict[str, object] = {"chat_id": telegram_id, "text": message}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    try:
        async with httpx.AsyncClient(timeout=8, transport=transport) as client:
            response = await client.post(
                f"{TELEGRAM_API_BASE}/bot{token}/sendMessage",
                json=payload,
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


async def notify_admins(message: str, *, reply_markup: dict[str, object] | None = None) -> None:
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
        await send_telegram_message(admin_id, message, reply_markup=reply_markup)


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
    if booking.promo_code:
        lines.append(f"Промокод: {booking.promo_code}")
    if booking.comment:
        lines.append(f"Комментарий: {booking.comment}")
    lines.append(f"Заявка #{booking.id}")
    return "\n".join(lines)


def user_booking_notification(booking: Booking, title: str, message: str) -> UserNotification:
    return UserNotification(user_id=booking.user_id, type="booking_status", title=title, message=message)


#: Nominative months would read "27 август"; the message needs the genitive.
_RU_MONTHS = (
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)


def format_date(show_date: str) -> str:
    """"2026-08-27" -> "27 августа". Unparseable input is passed through."""
    from datetime import date

    try:
        day = date.fromisoformat(show_date)
    except ValueError:
        return show_date
    return f"{day.day} {_RU_MONTHS[day.month - 1]}"


def format_money(amount: int, currency: str) -> str:
    """"90 000 сум" -- grouped the way the price is written on the wall."""
    grouped = f"{amount:,}".replace(",", "\u00a0")
    return f"{grouped} сум" if currency.upper() == "UZS" else f"{grouped} {currency}"


def _summary(booking: Booking, currency: str) -> list[str]:
    return [
        f"Дата: {format_date(booking.show_date)}",
        f"Время: {booking.session}",
        f"Гостей: {booking.party_size}",
        f"Сумма: {format_money(booking.total, currency)}",
    ]


def generic_booking_admin_message(booking: Booking, currency: str = "UZS") -> str:
    """What the administrator receives for a request with no film attached.

    The mini app books places, not a screening, so there is deliberately no
    film line here: the administrator agrees the film in the callback.
    """
    name = " ".join(part for part in (booking.first_name, booking.last_name) if part) or "Без имени"
    lines = ["Новая заявка на бронирование", *_summary(booking, currency), f"Клиент: {name}"]
    lines.append(f"Телефон: {booking.phone}")
    if booking.telegram_username:
        lines.append(f"Telegram: @{booking.telegram_username}")
    if booking.promo_code:
        lines.append(f"Промокод: {booking.promo_code}")
    if booking.comment:
        lines.append(f"Комментарий: {booking.comment}")
    lines.append(f"Заявка #{booking.id}")
    return "\n".join(lines)


def _admin_contacts(settings) -> list[str]:
    lines = []
    if settings.admin_phone:
        lines.append(f"Телефон: {settings.admin_phone}")
    if settings.admin_telegram:
        lines.append(f"Telegram: {settings.admin_telegram}")
    return lines


def generic_booking_user_message(booking: Booking, settings) -> str:
    """The acknowledgement the viewer sees the moment the request is filed.

    It has to be honest about what was and was not reserved, or the viewer will
    read "booked" as "my film at my seat is guaranteed".
    """
    return "\n".join(
        [
            f"Заявка №{booking.id} принята",
            "",
            *_summary(booking, settings.currency),
            "",
            "Вы бронируете количество мест без выбора конкретного ряда и кресла.",
            "Фильм не закрепляется автоматически: его и оплату согласует администратор.",
            "Мы свяжемся с вами для подтверждения.",
            *(["", *_admin_contacts(settings)] if _admin_contacts(settings) else []),
        ]
    )


def generic_booking_confirmed_message(booking: Booking, settings) -> str:
    """The confirmation, with both contacts and no promise about the film."""
    return "\n".join(
        [
            f"Бронирование №{booking.id} подтверждено",
            "",
            *_summary(booking, settings.currency),
            "",
            "Вы забронировали количество мест без выбора конкретного ряда и кресла.",
            "Фильм не закрепляется автоматически. Выберите подходящий фильм в каталоге "
            "и согласуйте детали и оплату с администратором.",
            *(["", *_admin_contacts(settings)] if _admin_contacts(settings) else []),
        ]
    )


# --- the administrator's own workflow: buttons in the bot's DM ----------------
#
# The client wants the everyday work to happen in Telegram itself: the request
# notification carries real inline buttons, so the administrator never has to
# open the Mini App to move a request along. The panel keeps working exactly
# as before -- both surfaces call the same `apply_decision` in
# `backend.services.booking_decisions`; this module only draws the keyboard.

_STATUS_LABELS = {
    "pending": "Ожидает",
    "contacting": "В обработке",
    "confirmed": "Подтверждена",
    "cancelled": "Отклонена",
    "watched": "Состоялась",
}

#: Actions offered for each still-open status. A settled request (confirmed,
#: cancelled, watched) offers none -- there is nothing left to relitigate.
_ACTIONS_FOR_STATUS = {
    "pending": (("contact", "Начать обработку"), ("confirm", "Подтвердить"), ("propose", "Предложить время"), ("decline", "Отклонить")),
    "contacting": (("confirm", "Подтвердить"), ("propose", "Предложить время"), ("decline", "Отклонить")),
}


def admin_action_keyboard(
    booking_id: int,
    status: str,
    *,
    telegram_username: str = "",
    telegram_id: int | None = None,
) -> dict[str, object]:
    """The buttons under a request the administrator can still act on.

    A `url` chat button is included whenever there is somewhere to send it:
    a public `@username` opens `t.me/username`, and a viewer with none is
    still reachable at `tg://user?id=...` from the same Telegram client.
    """
    rows: list[list[dict[str, object]]] = [
        [{"text": label, "callback_data": f"bk:{action}:{booking_id}"}]
        for action, label in _ACTIONS_FOR_STATUS.get(status, ())
    ]
    handle = telegram_username.strip().lstrip("@")
    if handle:
        rows.append([{"text": "Открыть чат", "url": f"https://t.me/{handle}"}])
    elif telegram_id:
        rows.append([{"text": "Открыть чат", "url": f"tg://user?id={telegram_id}"}])
    return {"inline_keyboard": rows}


def admin_propose_time_keyboard(booking_id: int, times: list[str]) -> dict[str, object]:
    """One fixed time per button, plus a way back to the main actions."""
    rows = [[{"text": time, "callback_data": f"bk:proposetime:{booking_id}:{time}"}] for time in times]
    rows.append([{"text": "Назад", "callback_data": f"bk:cancelpropose:{booking_id}"}])
    return {"inline_keyboard": rows}


def viewer_proposal_keyboard(booking_id: int) -> dict[str, object]:
    """What the viewer taps to answer a proposed time: `pr:accept:<id>` / `pr:decline:<id>`.

    Namespaced `pr:` rather than `bk:` so the bot's single callback dispatcher
    can tell "the administrator is deciding a request" apart from "the viewer
    is answering a proposal" without inspecting who pressed the button.
    """
    return {
        "inline_keyboard": [
            [
                {"text": "Принять", "callback_data": f"pr:accept:{booking_id}"},
                {"text": "Отклонить", "callback_data": f"pr:decline:{booking_id}"},
            ]
        ]
    }


def admin_action_card(result) -> str:
    """The text the administrator reads above the buttons.

    `result` is a `backend.services.booking_decisions.DecisionResult` (or
    anything with the same attributes) -- accepted duck-typed so this module
    never has to import that one and risk a cycle.
    """
    lines = [f"Заявка #{result.booking_id}", f"Статус: {_STATUS_LABELS.get(result.status, result.status)}"]
    if result.movie_title:
        lines.append(f"Фильм: {result.movie_title}")
    else:
        lines.append("Фильм согласуется с администратором лично")
    lines.append(f"Дата: {format_date(result.show_date)} {result.session_time}")
    lines.append(f"Гостей: {result.party_size}")
    lines.append(f"Сумма: {format_money(result.total, 'UZS')}")
    lines.append(f"Телефон: {result.phone}")
    if result.telegram_username:
        lines.append(f"Telegram: @{result.telegram_username}")
    if result.proposed_session:
        lines.append(f"Предложено время: {result.proposed_session}")
    if result.admin_note:
        lines.append(f"Заметка: {result.admin_note}")
    return "\n".join(lines)
