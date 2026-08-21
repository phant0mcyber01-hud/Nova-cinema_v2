"""Admin CRUD for bonuses, melodies and the gallery (spec 4.6, 4.7, 16)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import admin_required, get_db
from backend.core.config import MAX_MELODIES
from backend.models import Bonus, GalleryImage, Melody
from backend.schemas.settings import BonusIn, GalleryImageIn, MelodyIn, MelodyPatchIn
from backend.services.media import save_audio_upload

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


def _melody(item: Melody) -> dict[str, object]:
    return {"id": item.id, "title": item.title, "file_url": item.file_url, "sort_order": item.sort_order}


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


# --- melodies ----------------------------------------------------------------


@router.get("/melodies")
async def list_melodies(session: AsyncSession = Depends(get_db)) -> list[dict[str, object]]:
    rows = await session.scalars(select(Melody).order_by(Melody.sort_order, Melody.id))
    return [_melody(item) for item in rows]


@router.post("/melodies/upload")
async def upload_melody(file: UploadFile = File(...)) -> dict[str, str]:
    return {"url": await save_audio_upload(file)}


@router.post("/melodies")
async def create_melody(payload: MelodyIn, session: AsyncSession = Depends(get_db)) -> dict[str, object]:
    count = await session.scalar(select(func.count()).select_from(Melody)) or 0
    if count >= MAX_MELODIES:
        raise HTTPException(409, f"At most {MAX_MELODIES} melodies are allowed")
    item = Melody(**payload.model_dump())
    session.add(item)
    await session.commit()
    return {"id": item.id}


@router.patch("/melodies/{melody_id}")
async def edit_melody(
    melody_id: int, payload: MelodyPatchIn, session: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    """Rename or replace the audio without deleting and re-adding the row."""
    item = await session.get(Melody, melody_id)
    if item is None:
        raise HTTPException(404, "Melody not found")
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(item, key, value)
    await session.commit()
    return {"status": "updated"}


@router.delete("/melodies/{melody_id}")
async def delete_melody(melody_id: int, session: AsyncSession = Depends(get_db)) -> dict[str, str]:
    item = await session.get(Melody, melody_id)
    if item is None:
        raise HTTPException(404, "Melody not found")
    await session.delete(item)
    await session.commit()
    return {"status": "deleted"}


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
