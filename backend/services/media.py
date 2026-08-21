"""Trailer id parsing and validated image uploads."""
from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from fastapi import HTTPException, UploadFile

from backend.core.config import AUDIO_MAX_BYTES, UPLOAD_DIR, UPLOAD_MAX_BYTES

IMAGE_SIGNATURES = {
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".webp": (b"RIFF",),
}


def youtube_video_id(value: str) -> str:
    source = value.strip()
    if not source:
        return source
    parsed = urlparse(source)
    if parsed.netloc:
        host = parsed.netloc.lower().removeprefix("www.")
        if host == "youtu.be":
            source = parsed.path.strip("/").split("/")[0]
        elif host in {"youtube.com", "m.youtube.com", "music.youtube.com", "youtube-nocookie.com"}:
            query_id = parse_qs(parsed.query).get("v", [""])[0]
            path_parts = [part for part in parsed.path.split("/") if part]
            if query_id:
                source = query_id
            elif len(path_parts) >= 2 and path_parts[0] in {"embed", "shorts", "live"}:
                source = path_parts[1]
            else:
                source = path_parts[-1] if path_parts else ""
    source = source.strip()
    if not source or any(symbol in source for symbol in "/?&#=") or len(source) > 32:
        raise ValueError("Invalid YouTube trailer URL or video id")
    return source


async def save_image_upload(file: UploadFile) -> str:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(422, "Only image uploads are allowed")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in IMAGE_SIGNATURES:
        raise HTTPException(422, "Unsupported image format")
    content = await file.read()
    if len(content) > UPLOAD_MAX_BYTES:
        raise HTTPException(413, "Image is too large")
    if not any(content.startswith(signature) for signature in IMAGE_SIGNATURES[suffix]):
        raise HTTPException(422, "Invalid image content")
    if suffix == ".webp" and content[8:12] != b"WEBP":
        raise HTTPException(422, "Invalid image content")
    filename = f"{uuid.uuid4().hex}{suffix}"
    await asyncio.to_thread((UPLOAD_DIR / filename).write_bytes, content)
    return f"/uploads/{filename}"


AUDIO_SUFFIXES = {".mp3", ".ogg", ".m4a", ".wav"}


def _looks_like_audio(suffix: str, content: bytes) -> bool:
    """Signature check so the extension alone cannot smuggle in another format."""
    if suffix == ".mp3":
        return content.startswith(b"ID3") or (len(content) > 1 and content[0] == 0xFF and content[1] & 0xE0 == 0xE0)
    if suffix == ".ogg":
        return content.startswith(b"OggS")
    if suffix == ".m4a":
        return content[4:8] == b"ftyp"
    if suffix == ".wav":
        return content.startswith(b"RIFF") and content[8:12] == b"WAVE"
    return False


async def save_audio_upload(file: UploadFile) -> str:
    """Validated melody upload (spec 4.7): no hardcoded audio files in the repo."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in AUDIO_SUFFIXES:
        raise HTTPException(422, "Unsupported audio format")
    content = await file.read()
    if len(content) > AUDIO_MAX_BYTES:
        raise HTTPException(413, "Audio file is too large")
    if not _looks_like_audio(suffix, content):
        raise HTTPException(422, "Invalid audio content")
    filename = f"{uuid.uuid4().hex}{suffix}"
    await asyncio.to_thread((UPLOAD_DIR / filename).write_bytes, content)
    return f"/uploads/{filename}"
