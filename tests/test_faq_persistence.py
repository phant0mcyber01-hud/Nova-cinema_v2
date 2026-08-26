"""FAQ and the "important to know" note actually save and come back.

The admin form has always had inputs for these -- they simply had nowhere to
land: no column on `cinema_settings`, no field on `SettingsIn`, so PUT
/api/admin/settings silently dropped them (pydantic ignores unknown model
fields) and the panel looked like it saved when it had not written anything.

The client asked for FAQ content; writing FAQ that vanishes on save is worse
than no FAQ, so this is fixed before any content goes in.
"""
from __future__ import annotations

from tests.conftest import ADMIN_ID, auth_header, login


async def _admin_settings(client, token):
    return (await client.get("/api/admin/settings", headers=auth_header(token))).json()


async def test_important_note_and_faq_round_trip_through_the_admin_form(client):
    admin = await login(client, ADMIN_ID, "admin")
    current = await _admin_settings(client, admin)
    current.pop("hall_seats", None)
    current.pop("updated_at", None)
    current["important"] = "Оплата только переводом администратору."
    current["important_uz"] = "Toʻlov faqat administratorga oʻtkazma orqali."
    current["faq"] = [
        {
            "question_ru": "Как оплатить бронь?",
            "answer_ru": "Администратор пришлёт реквизиты после подтверждения.",
            "question_uz": "Bronni qanday toʻlayman?",
            "answer_uz": "Administrator tasdiqlagandan keyin rekvizitlarni yuboradi.",
        },
        {
            "question_ru": "Можно выбрать фильм заранее?",
            "answer_ru": "Фильм согласуется с администратором после заявки.",
            "question_uz": "Filmni oldindan tanlasa boʻladimi?",
            "answer_uz": "Film ariza berilgandan keyin administrator bilan kelishiladi.",
        },
    ]

    saved = await client.put("/api/admin/settings", json=current, headers=auth_header(admin))
    assert saved.status_code == 200, saved.text
    assert saved.json()["important"] == current["important"]
    assert len(saved.json()["faq"]) == 2

    # Not just the same response -- a fresh read must show it too.
    reread = await _admin_settings(client, admin)
    assert reread["important"] == current["important"]
    assert reread["faq"] == current["faq"]


async def test_the_public_settings_endpoint_serves_faq_localised(client):
    admin = await login(client, ADMIN_ID, "admin")
    current = await _admin_settings(client, admin)
    current.pop("hall_seats", None)
    current.pop("updated_at", None)
    current["important"] = "Важно знать"
    current["important_uz"] = "Muhim maʼlumot"
    current["faq"] = [
        {
            "question_ru": "Вопрос по-русски",
            "answer_ru": "Ответ по-русски",
            "question_uz": "Savol oʻzbekcha",
            "answer_uz": "Javob oʻzbekcha",
        },
    ]
    await client.put("/api/admin/settings", json=current, headers=auth_header(admin))

    ru = (await client.get("/api/settings")).json()
    assert ru["important"] == "Важно знать"
    assert ru["faq"] == [{"question": "Вопрос по-русски", "answer": "Ответ по-русски"}]

    uz = (await client.get("/api/settings", params={"lang": "uz"})).json()
    assert uz["important"] == "Muhim maʼlumot"
    assert uz["faq"] == [{"question": "Savol oʻzbekcha", "answer": "Javob oʻzbekcha"}]


async def test_faq_is_capped_so_the_admin_cannot_post_an_unbounded_list(client):
    admin = await login(client, ADMIN_ID, "admin")
    current = await _admin_settings(client, admin)
    current.pop("hall_seats", None)
    current.pop("updated_at", None)
    current["faq"] = [
        {"question_ru": f"Q{i}", "answer_ru": f"A{i}", "question_uz": "", "answer_uz": ""}
        for i in range(50)
    ]
    response = await client.put("/api/admin/settings", json=current, headers=auth_header(admin))
    assert response.status_code == 422


async def test_seeded_settings_carry_no_faq_until_the_admin_writes_some(client):
    """A fresh cinema shows no FAQ block rather than placeholder junk."""
    data = (await client.get("/api/settings")).json()
    assert data["faq"] == []
    assert data["important"] == ""
