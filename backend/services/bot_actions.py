"""What happens when the administrator taps a button on a request's card.

The card lives in the admin's own Telegram DM: `bk:<action>:<booking_id>`, plus
`bk:proposetime:<id>:<time>` and `bk:cancelpropose:<id>` for the two-step "pick
a fixed time" flow. Nothing here talks to aiogram directly -- it returns a
plain `CallbackOutcome` describing what to edit and who else to message, so it
is testable with a database session alone and `bot.py` only has to wire the
result to the Telegram objects.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.booking_decisions import (
    BookingNotFound,
    DecisionResult,
    HallIsFull,
    ProposalNotFound,
    ProposedTimeRequired,
    SeatsAlreadyTaken,
    answer_proposal,
    apply_decision,
)
from backend.services.slots import active_slot_times
from backend.services.telegram import (
    admin_action_card,
    admin_action_keyboard,
    admin_propose_time_keyboard,
    notify_admins,
    viewer_proposal_keyboard,
)

__all__ = ["CallbackOutcome", "handle_booking_callback", "handle_proposal_callback"]


@dataclass
class CallbackOutcome:
    """What the bot does after one button press.

    `edit_text`/`edit_keyboard` are applied to the message the button was on
    (`None` means leave that part alone). `viewer_telegram_id`/`viewer_message`
    is the separate message to the person who filed the request, if any.
    """

    edit_text: str | None = None
    edit_keyboard: dict[str, object] | None = None
    viewer_telegram_id: int | None = None
    viewer_message: str | None = None
    #: Buttons attached to the viewer's own message (currently only the
    #: Accept/Decline pair after a proposed time). `None` means plain text.
    viewer_keyboard: dict[str, object] | None = None
    show_alert: bool = False
    alert: str = ""


def _card_and_keyboard(result: DecisionResult) -> tuple[str, dict[str, object]]:
    return admin_action_card(result), admin_action_keyboard(
        result.booking_id, result.status, telegram_username=result.telegram_username
    )


async def handle_booking_callback(session: AsyncSession, data: str) -> CallbackOutcome:
    """Route one `bk:...` callback_data string to its effect.

    Every branch is defensive about a booking that no longer exists or a hall
    that filled up between the notification and the tap: those become a quiet
    alert on the button press itself, never a crash the administrator sees as
    "something went wrong" with no further information.
    """
    parts = data.split(":")
    if len(parts) < 3 or parts[0] != "bk":
        return CallbackOutcome(show_alert=True, alert="Неизвестная команда")

    action = parts[1]
    try:
        booking_id = int(parts[2])
    except ValueError:
        return CallbackOutcome(show_alert=True, alert="Неизвестная заявка")

    if action == "propose":
        # Show the fixed times to choose from; nothing is decided yet.
        times = list(await active_slot_times(session))
        return CallbackOutcome(edit_keyboard=admin_propose_time_keyboard(booking_id, times))

    if action == "cancelpropose":
        # Changed their mind before picking a time -- back to the main actions.
        # The status is unknown here without a lookup, so ask the database.
        from backend.models import Booking

        booking = await session.get(Booking, booking_id)
        if booking is None:
            return CallbackOutcome(show_alert=True, alert="Заявка не найдена")
        return CallbackOutcome(
            edit_keyboard=admin_action_keyboard(
                booking_id, booking.status, telegram_username=booking.telegram_username
            )
        )

    if action == "proposetime":
        if len(parts) < 4:
            return CallbackOutcome(show_alert=True, alert="Не выбрано время")
        # The time itself contains a colon ("20:00"), so everything after the
        # booking id is the time -- `split(":", 3)` up top would also work,
        # but rejoining here keeps the id parsing above uniform for every action.
        proposed_time = ":".join(parts[3:])
        try:
            result = await apply_decision(session, booking_id, "propose", proposed_session=proposed_time)
        except BookingNotFound:
            return CallbackOutcome(show_alert=True, alert="Заявка не найдена")
        except HallIsFull:
            return CallbackOutcome(show_alert=True, alert="Зал уже заполнен на это время")
        text, keyboard = _card_and_keyboard(result)
        return CallbackOutcome(
            edit_text=text,
            edit_keyboard=keyboard,
            viewer_telegram_id=result.viewer_telegram_id,
            viewer_message=result.viewer_message,
            viewer_keyboard=viewer_proposal_keyboard(booking_id),
        )

    if action not in ("contact", "confirm", "decline"):
        return CallbackOutcome(show_alert=True, alert="Неизвестное действие")

    try:
        result = await apply_decision(session, booking_id, action)
    except BookingNotFound:
        return CallbackOutcome(show_alert=True, alert="Заявка не найдена")
    except HallIsFull:
        return CallbackOutcome(show_alert=True, alert="Зал уже заполнен на это время")
    except SeatsAlreadyTaken as error:
        return CallbackOutcome(show_alert=True, alert=str(error))

    text, keyboard = _card_and_keyboard(result)
    return CallbackOutcome(
        edit_text=text,
        edit_keyboard=keyboard,
        viewer_telegram_id=result.viewer_telegram_id,
        viewer_message=result.viewer_message,
    )


async def handle_proposal_callback(session: AsyncSession, telegram_id: int, data: str) -> CallbackOutcome:
    """Route the viewer's own `pr:accept:<id>` / `pr:decline:<id>` tap.

    `telegram_id` is the id of whoever pressed the button -- passed in rather
    than trusted from the callback data, so answering somebody else's proposal
    is refused even if the booking id is guessed. This edits the viewer's own
    message (buttons removed once answered) and separately tells the admins,
    exactly as the panel's own accept/decline endpoint always did.
    """
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != "pr" or parts[1] not in ("accept", "decline"):
        return CallbackOutcome(show_alert=True, alert="Неизвестная команда")
    action = parts[1]
    try:
        booking_id = int(parts[2])
    except ValueError:
        return CallbackOutcome(show_alert=True, alert="Неизвестная заявка")

    try:
        result = await answer_proposal(session, booking_id, telegram_id, action)
    except (BookingNotFound, ProposalNotFound):
        return CallbackOutcome(show_alert=True, alert="Это предложение вам недоступно")
    except HallIsFull:
        return CallbackOutcome(show_alert=True, alert="Зал уже заполнен на это время")
    except SeatsAlreadyTaken as error:
        return CallbackOutcome(show_alert=True, alert=str(error))

    # Same rule the panel's own endpoint follows: the admins get a live copy,
    # and a delivery failure never touches the answer already committed above.
    await notify_admins(result.admin_message)
    # The buttons are removed either way: answered once, the offer is settled.
    return CallbackOutcome(edit_text=result.viewer_message, edit_keyboard={"inline_keyboard": []})
