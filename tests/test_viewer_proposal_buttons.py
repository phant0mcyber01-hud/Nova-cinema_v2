"""When the admin proposes a new time, the viewer answers with buttons in the bot.

`generic_booking_confirmed_message` etc already carry no seat/film promise;
this is the missing piece for `propose`: the viewer's own DM must let them
accept or decline right there, not require them to reopen a Mini App screen
that no longer has a bookings section to react from.

`/api/profile/bookings/{id}/proposal` (accept/decline) is the existing,
already-tested endpoint both the button press and any residual client call
land on -- this file only proves the *keyboard* that reaches the viewer, and
that both places a proposal can be made from (the panel's /decision and the
bot's own proposetime picker) attach it.
"""
from __future__ import annotations

from backend.services.telegram import viewer_proposal_keyboard
from tests.conftest import ADMIN_ID, OTHER_ID, USER_ID, auth_header, login
from tests.test_generic_booking import book


def _callbacks(keyboard: dict) -> list[str]:
    return [button["callback_data"] for row in keyboard["inline_keyboard"] for button in row if "callback_data" in button]


# --- the keyboard shape ---------------------------------------------------


def test_the_viewer_gets_accept_and_decline_buttons():
    keyboard = viewer_proposal_keyboard(42)
    assert _callbacks(keyboard) == ["pr:accept:42", "pr:decline:42"]


# --- both places a proposal is made from attach it ----------------------------


async def test_the_panels_own_decision_endpoint_sends_the_viewer_a_keyboard(client, telegram_outbox):
    token = await login(client, USER_ID)
    booking = await book(client, token, 2)
    admin = await login(client, ADMIN_ID, "admin")
    telegram_outbox.clear()

    response = await client.patch(
        f"/api/admin/bookings/{booking['id']}/decision",
        json={"action": "propose", "reason": "", "proposed_session": "20:00"},
        headers=auth_header(admin),
    )
    assert response.status_code == 200, response.text

    import json

    request = next(item for item in telegram_outbox if json.loads(item.content)["chat_id"] == USER_ID)
    body = json.loads(request.content)
    assert _callbacks(body["reply_markup"]) == [f"pr:accept:{booking['id']}", f"pr:decline:{booking['id']}"]


async def test_the_bots_own_proposetime_picker_sends_the_viewer_a_keyboard(client, telegram_outbox):
    from backend.core.db import SessionLocal
    from backend.services.bot_actions import handle_booking_callback

    token = await login(client, USER_ID)
    booking = await book(client, token, 2)

    async with SessionLocal() as session:
        outcome = await handle_booking_callback(session, f"bk:proposetime:{booking['id']}:20:00")

    assert outcome.viewer_keyboard is not None
    assert _callbacks(outcome.viewer_keyboard) == [f"pr:accept:{booking['id']}", f"pr:decline:{booking['id']}"]


# --- the viewer's own accept/decline buttons ----------------------------------


async def test_the_viewer_accepting_moves_the_booking_and_notifies_the_admin(client, telegram_outbox):
    from backend.core.db import SessionLocal
    from backend.services.bot_actions import handle_proposal_callback

    token = await login(client, USER_ID)
    booking = await book(client, token, 2)
    admin = await login(client, ADMIN_ID, "admin")
    await client.patch(
        f"/api/admin/bookings/{booking['id']}/decision",
        json={"action": "propose", "reason": "", "proposed_session": "20:00"},
        headers=auth_header(admin),
    )
    telegram_outbox.clear()

    async with SessionLocal() as session:
        outcome = await handle_proposal_callback(session, USER_ID, f"pr:accept:{booking['id']}")

    assert outcome.show_alert is False
    assert "20:00" in (outcome.edit_text or "")
    assert telegram_outbox.chat_ids() == [ADMIN_ID]


async def test_the_viewer_declining_cancels_the_request_and_notifies_the_admin(client, telegram_outbox):
    from backend.core.db import SessionLocal
    from backend.models import Booking
    from backend.services.bot_actions import handle_proposal_callback

    token = await login(client, USER_ID)
    booking = await book(client, token, 2)
    admin = await login(client, ADMIN_ID, "admin")
    await client.patch(
        f"/api/admin/bookings/{booking['id']}/decision",
        json={"action": "propose", "reason": "", "proposed_session": "20:00"},
        headers=auth_header(admin),
    )
    telegram_outbox.clear()

    async with SessionLocal() as session:
        outcome = await handle_proposal_callback(session, USER_ID, f"pr:decline:{booking['id']}")

    assert outcome.show_alert is False
    async with SessionLocal() as session:
        row = await session.get(Booking, booking["id"])
    assert row.status == "cancelled"
    assert telegram_outbox.chat_ids() == [ADMIN_ID]


async def test_a_stranger_cannot_answer_somebody_elses_proposal(client, telegram_outbox):
    """Defence in depth: only the message's own recipient can act on it."""
    from backend.core.db import SessionLocal
    from backend.services.bot_actions import handle_proposal_callback

    token = await login(client, USER_ID)
    booking = await book(client, token, 2)
    admin = await login(client, ADMIN_ID, "admin")
    await client.patch(
        f"/api/admin/bookings/{booking['id']}/decision",
        json={"action": "propose", "reason": "", "proposed_session": "20:00"},
        headers=auth_header(admin),
    )

    async with SessionLocal() as session:
        outcome = await handle_proposal_callback(session, OTHER_ID, f"pr:accept:{booking['id']}")
    assert outcome.show_alert is True


async def test_answering_a_proposal_that_has_none_is_a_quiet_alert(client):
    from backend.core.db import SessionLocal
    from backend.services.bot_actions import handle_proposal_callback

    token = await login(client, USER_ID)
    booking = await book(client, token, 2)

    async with SessionLocal() as session:
        outcome = await handle_proposal_callback(session, USER_ID, f"pr:accept:{booking['id']}")
    assert outcome.show_alert is True
