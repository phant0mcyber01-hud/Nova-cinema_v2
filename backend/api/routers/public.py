"""Read-only endpoints for admin-managed content.

The Mini App and the bot both read the cinema profile from here instead of
carrying hardcoded contacts.
"""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_db
from backend.models import Bonus, GalleryImage, Melody
from backend.services.i18n import normalize_language
from backend.services.settings import get_settings, serialize_settings

router = APIRouter(prefix="/api", tags=["public"])


@router.get("/settings")
async def public_settings(lang: str = "ru", session: AsyncSession = Depends(get_db)) -> dict[str, object]:
    settings = await get_settings(session)
    data = serialize_settings(settings, lang)
    today = date.today()
    data["booking_dates"] = [
        (today + timedelta(days=offset)).isoformat() for offset in range(settings.booking_days_ahead)
    ]
    return data


@router.get("/bonuses")
async def public_bonuses(lang: str = "ru", session: AsyncSession = Depends(get_db)) -> list[dict[str, object]]:
    uz = normalize_language(lang) == "uz"
    rows = await session.scalars(
        select(Bonus).where(Bonus.is_active.is_(True)).order_by(Bonus.sort_order, Bonus.id)
    )
    return [
        {
            "id": item.id,
            "title": (item.title_uz or item.title) if uz else item.title,
            "text": (item.text_uz or item.text) if uz else item.text,
        }
        for item in rows
    ]


@router.get("/melodies")
async def public_melodies(session: AsyncSession = Depends(get_db)) -> list[dict[str, object]]:
    rows = await session.scalars(select(Melody).order_by(Melody.sort_order, Melody.id))
    return [{"id": item.id, "title": item.title, "file_url": item.file_url} for item in rows]


@router.get("/gallery")
async def public_gallery(lang: str = "ru", session: AsyncSession = Depends(get_db)) -> list[dict[str, object]]:
    uz = normalize_language(lang) == "uz"
    rows = await session.scalars(select(GalleryImage).order_by(GalleryImage.sort_order, GalleryImage.id))
    return [
        {
            "id": item.id,
            "image_url": item.image_url,
            "caption": (item.caption_uz or item.caption) if uz else item.caption,
        }
        for item in rows
    ]
