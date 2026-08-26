"""Replace the current catalog with the curated eight-movie lineup."""
from __future__ import annotations

import asyncio
import json
from datetime import timedelta
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import delete, func, select

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env", override=False, encoding="utf-8-sig")

from backend.core.config import DEFAULT_TIMEZONE_OFFSET_MINUTES
from backend.core.db import SessionLocal
from backend.models import (
    AdminNotification,
    Booking,
    Favorite,
    Movie,
    Review,
    SeatHold,
    Show,
)
from backend.services.booking import cinema_now

SHOW_TIMES = ("11:00", "14:30", "18:00", "21:30")


def movie(payload: dict[str, Any]) -> dict[str, Any]:
    """Map one JSON entry to the columns used by the Movie ORM model."""
    return {
        "title": payload["title"],
        "genre": payload["genre"],
        "description": payload["description"],
        "poster": payload["poster"],
        "gallery_json": json.dumps(payload["gallery"], ensure_ascii=False),
        "trailer_id": payload["trailer_id"],
        "duration": payload["duration"],
        "age": payload["age"],
        "year": payload["year"],
        "country": payload["country"],
        "director": payload["director"],
        "cast_json": json.dumps(payload["cast"], ensure_ascii=False),
        "imdb": payload["imdb"],
        "kinopoisk": payload["kinopoisk"],
        "internal_rating": payload["internal_rating"],
        "ticket_price": None,
        "is_published": True,
        "is_new": False,
        "new_until": "",
        "is_hit": True,
        "sort_order": payload["sort_order"],
    }


async def replace_catalog() -> None:
    payloads = json.loads((ROOT / "new_catalog_data.json").read_text(encoding="utf-8"))
    if not isinstance(payloads, list) or len(payloads) != 8:
        raise ValueError("new_catalog_data.json must contain exactly 8 movies")

    first_day = cinema_now(DEFAULT_TIMEZONE_OFFSET_MINUTES).date()
    async with SessionLocal() as session:
        async with session.begin():
            # Dependants must go first. Favorites is also a direct Movie FK.
            for model in (
                SeatHold,
                AdminNotification,
                Booking,
                Favorite,
                Review,
                Show,
                Movie,
            ):
                await session.execute(delete(model))

            for payload in payloads:
                item = Movie(**movie(payload))
                session.add(item)
                await session.flush()
                session.add_all(
                    Show(
                        movie_id=item.id,
                        show_date=(first_day + timedelta(days=offset)).isoformat(),
                        start_time=SHOW_TIMES[offset - 1],
                    )
                    for offset in range(1, 5)
                )

        movie_count = await session.scalar(select(func.count()).select_from(Movie))
        show_count = await session.scalar(select(func.count()).select_from(Show))
        hit_count = await session.scalar(select(func.count()).select_from(Movie).where(Movie.is_hit.is_(True)))
    print(f"Catalog replacement complete: movies={movie_count}, shows={show_count}, hits={hit_count}")


if __name__ == "__main__":
    asyncio.run(replace_catalog())
