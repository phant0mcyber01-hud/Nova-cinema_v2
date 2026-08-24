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


CHUNK_BYTES = 64 * 1024


async def _read_capped(file: UploadFile, limit: int, message: str) -> bytes:
    """Read the upload but stop as soon as it exceeds the limit.

    Reading the whole thing first and measuring afterwards means a caller
    decides how much the server buffers, which is the wrong way round.
    """
    chunks: list[bytes] = []
    size = 0
    while True:
        chunk = await file.read(CHUNK_BYTES)
        if not chunk:
            break
        size += len(chunk)
        if size > limit:
            raise HTTPException(413, message)
        chunks.append(chunk)
    return b"".join(chunks)


async def save_image_upload(file: UploadFile) -> str:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(422, "Only image uploads are allowed")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in IMAGE_SIGNATURES:
        raise HTTPException(422, "Unsupported image format")
    content = await _read_capped(file, UPLOAD_MAX_BYTES, "Image is too large")
    if not any(content.startswith(signature) for signature in IMAGE_SIGNATURES[suffix]):
        raise HTTPException(422, "Invalid image content")
    if suffix == ".webp" and content[8:12] != b"WEBP":
        raise HTTPException(422, "Invalid image content")
    filename = f"{uuid.uuid4().hex}{suffix}"
    await asyncio.to_thread((UPLOAD_DIR / filename).write_bytes, content)
    return f"/uploads/{filename}"


AUDIO_SUFFIXES = {".mp3", ".ogg", ".m4a", ".wav"}


def _strip_leading_id3v2(content: bytes) -> bytes:
    """Return MP3 bytes starting at the first audio frame.

    ID3v2 stores its payload size as four syncsafe bytes and excludes the
    ten-byte header from that size. ID3v2.4 may append a ten-byte footer. A
    malformed tag is rejected instead of slicing arbitrary audio bytes.
    """
    while content.startswith(b"ID3"):
        if len(content) < 10 or content[3] not in {2, 3, 4} or content[4] == 0xFF:
            raise ValueError("Invalid ID3v2 header")

        major, flags = content[3], content[5]
        allowed_flags = {2: 0xC0, 3: 0xE0, 4: 0xF0}[major]
        if flags & ~allowed_flags:
            raise ValueError("Invalid ID3v2 flags")

        size_bytes = content[6:10]
        if any(value & 0x80 for value in size_bytes):
            raise ValueError("Invalid ID3v2 syncsafe size")
        payload_size = (
            (size_bytes[0] << 21)
            | (size_bytes[1] << 14)
            | (size_bytes[2] << 7)
            | size_bytes[3]
        )
        footer_size = 10 if major == 4 and flags & 0x10 else 0
        tag_end = 10 + payload_size + footer_size
        if tag_end > len(content):
            raise ValueError("Truncated ID3v2 tag")
        if footer_size and content[tag_end - 10:tag_end] != b"3DI" + content[3:10]:
            raise ValueError("Invalid ID3v2 footer")
        content = content[tag_end:]
    return content


def _looks_like_mp3_frame(content: bytes) -> bool:
    """Validate the fixed fields of an MPEG audio frame header."""
    if len(content) < 4:
        return False
    header = int.from_bytes(content[:4], "big")
    version = (header >> 19) & 0x3
    layer = (header >> 17) & 0x3
    bitrate = (header >> 12) & 0xF
    sample_rate = (header >> 10) & 0x3
    emphasis = header & 0x3
    return (
        header >> 21 == 0x7FF
        and version != 0x1
        and layer != 0x0
        and bitrate not in {0x0, 0xF}
        and sample_rate != 0x3
        and emphasis != 0x2
    )


def _looks_like_audio(suffix: str, content: bytes) -> bool:
    """Signature check so the extension alone cannot smuggle in another format."""
    if suffix == ".mp3":
        return _looks_like_mp3_frame(content)
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
    content = await _read_capped(file, AUDIO_MAX_BYTES, "Audio file is too large")
    if suffix == ".mp3":
        try:
            content = _strip_leading_id3v2(content)
        except ValueError as error:
            raise HTTPException(422, "Invalid audio content") from error
    if not _looks_like_audio(suffix, content):
        raise HTTPException(422, "Invalid audio content")
    filename = f"{uuid.uuid4().hex}{suffix}"
    await asyncio.to_thread((UPLOAD_DIR / filename).write_bytes, content)
    return f"/uploads/{filename}"
