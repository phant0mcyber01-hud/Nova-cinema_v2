"""Replace the About paragraph with the five short bullets the client asked for.

The live text was typed into the admin panel, not seeded from the model default
(which is an empty string), so it only exists in the database — hence this
one-off script rather than a code change.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env", override=False, encoding="utf-8-sig")

from backend.core.db import SessionLocal
from backend.models import CinemaSettings

# One bullet per line: About.tsx renders a multi-line value as a list.
ABOUT_RU = "\n".join(
    [
        "Душевная атмосфера",
        "Полное погружение",
        "Камерный зал на 15 мест",
        "Премьеры и любимая классика",
        "Бронь в Telegram за минуту",
    ]
)
ABOUT_UZ = "\n".join(
    [
        "Samimiy muhit",
        "Toʻliq shoʻngʻish",
        "Atigi 15 oʻrinlik zal",
        "Premyeralar va sevimli klassika",
        "Telegramda bir daqiqada bron",
    ]
)


async def update_about_text() -> None:
    async with SessionLocal() as session:
        async with session.begin():
            settings = await session.get(CinemaSettings, 1)
            if settings is None:
                raise SystemExit("CinemaSettings id=1 not found: nothing to update")
            settings.about = ABOUT_RU
            settings.about_uz = ABOUT_UZ

        settings = await session.get(CinemaSettings, 1)
        print("about:")
        print(settings.about)
        print("about_uz:")
        print(settings.about_uz)


if __name__ == "__main__":
    asyncio.run(update_about_text())
