"""Admin CRUD for bonuses and the gallery (spec 4.6, 16)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import admin_required, get_db
from backend.models import Bonus, GalleryImage
from backend.schemas.settings import BonusIn, GalleryImageIn

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(admin_required)])


def _bonus(item: Bonus) -> dict[str, object]:
    return {
        "id": item.id,
        "title": item.title,
        "title_uz": item.title_uz,
        "text": item.text,
        "text_uz": item.text_uz,
        "is_active": item.is_active,
        "sort_order": item.sort_order,
    }



def _image(item: GalleryImage) -> dict[str, object]:
    return {
        "id": item.id,
        "image_url": item.image_url,
        "caption": item.caption,
        "caption_uz": item.caption_uz,
        "sort_order": item.sort_order,
    }


# --- bonuses -----------------------------------------------------------------


@router.get("/bonuses")
async def list_bonuses(session: AsyncSession = Depends(get_db)) -> list[dict[str, object]]:
    rows = await session.scalars(select(Bonus).order_by(Bonus.sort_order, Bonus.id))
    return [_bonus(item) for item in rows]


@router.post("/bonuses")
async def create_bonus(payload: BonusIn, session: AsyncSession = Depends(get_db)) -> dict[str, object]:
    item = Bonus(**payload.model_dump())
    session.add(item)
    await session.commit()
    return {"id": item.id}


@router.patch("/bonuses/{bonus_id}")
async def edit_bonus(bonus_id: int, payload: BonusIn, session: AsyncSession = Depends(get_db)) -> dict[str, str]:
    item = await session.get(Bonus, bonus_id)
    if item is None:
        raise HTTPException(404, "Bonus not found")
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    await session.commit()
    return {"status": "updated"}


@router.delete("/bonuses/{bonus_id}")
async def delete_bonus(bonus_id: int, session: AsyncSession = Depends(get_db)) -> dict[str, str]:
    item = await session.get(Bonus, bonus_id)
    if item is None:
        raise HTTPException(404, "Bonus not found")
    await session.delete(item)
    await session.commit()
    return {"status": "deleted"}


# The melody endpoints were removed with the feature: the audio player loaded
# the small box the cinema runs on, Telegram blocks autoplay anyway, and the
# client dropped it. The `melodies` table and any uploaded file are left alone
# on purpose -- this removes the API surface, not somebody's data.


# --- gallery -----------------------------------------------------------------


@router.get("/gallery")
async def list_gallery(session: AsyncSession = Depends(get_db)) -> list[dict[str, object]]:
    rows = await session.scalars(select(GalleryImage).order_by(GalleryImage.sort_order, GalleryImage.id))
    return [_image(item) for item in rows]


@router.post("/gallery")
async def create_image(payload: GalleryImageIn, session: AsyncSession = Depends(get_db)) -> dict[str, object]:
    item = GalleryImage(**payload.model_dump())
    session.add(item)
    await session.commit()
    return {"id": item.id}


@router.patch("/gallery/{image_id}")
async def edit_image(
    image_id: int, payload: GalleryImageIn, session: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    item = await session.get(GalleryImage, image_id)
    if item is None:
        raise HTTPException(404, "Image not found")
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    await session.commit()
    return {"status": "updated"}


@router.delete("/gallery/{image_id}")
async def delete_image(image_id: int, session: AsyncSession = Depends(get_db)) -> dict[str, str]:
    item = await session.get(GalleryImage, image_id)
    if item is None:
        raise HTTPException(404, "Image not found")
    await session.delete(item)
    await session.commit()
    return {"status": "deleted"}
