"""Stage 16: the data the About screen is built from.

Everything on that screen is admin-managed — the spec is explicit that the
owner must not need a developer to change an address or a phone number.
"""
from __future__ import annotations

from backend.core.db import SessionLocal
from backend.models import GalleryImage
from tests.conftest import ADMIN_ID, auth_header, login

ABOUT_FIELDS = (
    "name", "address", "phone", "telegram_url", "instagram_url",
    "map_url", "latitude", "longitude", "work_hours", "about",
)


async def test_settings_carry_everything_the_about_screen_shows(client):
    data = (await client.get("/api/settings")).json()
    for field in ABOUT_FIELDS:
        assert field in data, f"About screen is missing {field}"
    # The seeded contacts are the ones the spec lists.
    assert data["address"] == "Юксалиш 97А"
    assert data["phone"] == "+998 91 326 20 65"
    assert data["telegram_url"] == "https://t.me/novasinema"
    assert "instagram.com/nova_cinema__" in data["instagram_url"]


async def test_about_data_has_no_bar_prices_or_orders(client):
    """Spec 16 forbids adding bar prices and ordering to this section."""
    data = (await client.get("/api/settings")).json()
    for forbidden in ("bar_menu", "bar_prices", "menu", "order"):
        assert forbidden not in data


async def test_gallery_follows_the_admin_order(client):
    async with SessionLocal() as session:
        session.add_all([
            GalleryImage(image_url="/uploads/bar.jpg", caption="Бар", sort_order=2),
            GalleryImage(image_url="/uploads/hall.jpg", caption="Зал", sort_order=0),
            GalleryImage(image_url="/uploads/foyer.jpg", caption="Фойе", sort_order=1),
        ])
        await session.commit()

    captions = [item["caption"] for item in (await client.get("/api/gallery")).json()]
    assert captions == ["Зал", "Фойе", "Бар"]


async def test_gallery_is_empty_until_photos_are_uploaded(client):
    assert (await client.get("/api/gallery")).json() == []


async def test_admin_edits_the_whole_contact_block(client):
    """The owner changes an address without touching code — the point of stage 3."""
    admin = await login(client, ADMIN_ID, "admin")
    current = (await client.get("/api/admin/settings", headers=auth_header(admin))).json()
    current.pop("hall_seats", None)
    current.pop("updated_at", None)
    current.update({
        "address": "Юксалиш 100",
        "phone": "+998 90 111 22 33",
        "instagram_url": "https://www.instagram.com/nova_new",
        "map_url": "https://maps.google.com/?q=41.31,69.24",
        "latitude": 41.31,
        "longitude": 69.24,
        "work_hours": "09:00 - 02:00",
        "about": "Уютный зал на 15 мест.",
    })
    assert (await client.put("/api/admin/settings", json=current, headers=auth_header(admin))).status_code == 200

    public = (await client.get("/api/settings")).json()
    assert public["address"] == "Юксалиш 100"
    assert public["phone"] == "+998 90 111 22 33"
    assert public["latitude"] == 41.31
    assert public["work_hours"] == "09:00 - 02:00"
    assert public["about"] == "Уютный зал на 15 мест."


async def test_gallery_captions_follow_the_language(client):
    async with SessionLocal() as session:
        session.add(GalleryImage(image_url="/uploads/hall.jpg", caption="Зал", caption_uz="Zal"))
        await session.commit()

    assert (await client.get("/api/gallery")).json()[0]["caption"] == "Зал"
    assert (await client.get("/api/gallery", params={"lang": "uz"})).json()[0]["caption"] == "Zal"


async def test_gallery_is_public_but_editing_is_not(client):
    assert (await client.get("/api/gallery")).status_code == 200
    assert (await client.post("/api/admin/gallery", json={"image_url": "/x.jpg"})).status_code == 401


# --- stage 20: the content the About screen now renders ----------------------


async def test_bonuses_the_admin_switched_on_reach_the_about_screen(client):
    """A promotion nobody can read is the same as no promotion at all."""
    admin = await login(client, ADMIN_ID, "admin")
    for payload in (
        {"title": "Второй билет со скидкой", "title_uz": "Ikkinchi chipta chegirmali",
         "text": "Скидка 20% на второй билет", "text_uz": "Ikkinchi chiptaga 20% chegirma",
         "is_active": True, "sort_order": 2},
        {"title": "День рождения", "title_uz": "Tugʻilgan kun",
         "text": "Именинникам бесплатный попкорн", "text_uz": "Tugʻilgan kun egasiga bepul popkorn",
         "is_active": True, "sort_order": 1},
        {"title": "Закрытая акция", "title_uz": "", "text": "", "text_uz": "",
         "is_active": False, "sort_order": 3},
    ):
        assert (
            await client.post("/api/admin/bonuses", json=payload, headers=auth_header(admin))
        ).status_code == 200

    public = (await client.get("/api/bonuses")).json()
    assert [item["title"] for item in public] == ["День рождения", "Второй билет со скидкой"], (
        "the admin order decides, and a switched-off promotion stays hidden"
    )
    assert public[0]["text"] == "Именинникам бесплатный попкорн"

    uz = (await client.get("/api/bonuses", params={"lang": "uz"})).json()
    assert uz[0]["title"] == "Tugʻilgan kun"


async def test_melodies_the_admin_uploaded_reach_the_about_screen(client):
    admin = await login(client, ADMIN_ID, "admin")
    for title, url, order in (("Заставка", "/uploads/intro.mp3", 2), ("Антракт", "/uploads/break.mp3", 1)):
        response = await client.post(
            "/api/admin/melodies",
            json={"title": title, "file_url": url, "sort_order": order},
            headers=auth_header(admin),
        )
        assert response.status_code == 200

    public = (await client.get("/api/melodies")).json()
    assert [item["title"] for item in public] == ["Антракт", "Заставка"]
    assert public[0]["file_url"] == "/uploads/break.mp3", "the player needs a real source"


async def test_about_content_is_readable_without_signing_in(client):
    """The About screen is the first thing a stranger opens."""
    for path in ("/api/settings", "/api/gallery", "/api/bonuses", "/api/melodies"):
        assert (await client.get(path)).status_code == 200, path
