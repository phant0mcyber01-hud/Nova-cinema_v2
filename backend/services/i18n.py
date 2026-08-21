"""Language detection and RU/UZ translation of admin-entered movie fields."""
from __future__ import annotations

import json
import re

import httpx

from backend.core import config

TRANSLATED_FIELDS = ("title", "genre", "description", "country", "director")


def normalize_language(language: str) -> str:
    return "uz" if language.lower().startswith("uz") else "ru"


def detect_content_language(values: list[str]) -> str:
    text = " ".join(values)
    return "ru" if re.search(r"[А-Яа-яЁё]", text) else "uz"


async def translate_text(value: str, source: str, target: str) -> tuple[str, bool]:
    """Return (text, failed).  On any failure the original text is kept."""
    text = value.strip()
    if not text or source == target:
        return text, False
    if not config.TRANSLATION_API_URL:
        return text, True
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                config.TRANSLATION_API_URL,
                json={"q": text, "source": source, "target": target, "format": "text"},
            )
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError):
        return text, True
    translated = data.get("translatedText") if isinstance(data, dict) else None
    return (str(translated).strip() or text, False) if translated else (text, True)


async def localize_movie_payload(payload) -> tuple[dict[str, object], bool]:
    """Expand an admin movie payload into both RU and UZ column sets."""
    source = detect_content_language(
        [payload.title, payload.genre, payload.description, payload.country, payload.director, *payload.cast]
    )
    target = "uz" if source == "ru" else "ru"
    warning = False
    translated: dict[str, str] = {}
    for field in TRANSLATED_FIELDS:
        translated[field], failed = await translate_text(str(getattr(payload, field)), source, target)
        warning = warning or failed
    translated_cast: list[str] = []
    for item in payload.cast:
        value, failed = await translate_text(item, source, target)
        translated_cast.append(value)
        warning = warning or failed

    values = payload.model_dump(exclude={"cast", "gallery"})
    values.update({"cast_json": json.dumps(payload.cast), "gallery_json": json.dumps(payload.gallery)})
    original_cast = json.dumps(payload.cast)
    other_cast = json.dumps(translated_cast)

    if source == "ru":
        base, other = payload, translated
        base_cast, other_cast_json = original_cast, other_cast
    else:
        base, other = translated, payload
        base_cast, other_cast_json = other_cast, original_cast

    def value_of(holder, field: str) -> str:
        return holder[field] if isinstance(holder, dict) else str(getattr(holder, field))

    for field in TRANSLATED_FIELDS:
        values[field] = value_of(base, field)
        values[f"{field}_ru"] = value_of(base, field)
        values[f"{field}_uz"] = value_of(other, field)
    values["cast_json"] = base_cast
    values["cast_json_ru"] = base_cast
    values["cast_json_uz"] = other_cast_json
    return values, warning
