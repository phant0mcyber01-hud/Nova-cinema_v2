"""Trailer id parsing and validated image uploads."""
from __future__ import annotations

import asyncio
import json
import re
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import imageio_ffmpeg
from fastapi import HTTPException, UploadFile

from backend.core.config import (
    AUDIO_CHUNK_BYTES,
    AUDIO_MAX_BYTES,
    AUDIO_TRANSCODE_THRESHOLD_BYTES,
    UPLOAD_DIR,
    UPLOAD_MAX_BYTES,
)

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
AUDIO_UPLOAD_ID = re.compile(r"[0-9a-f]{32}")
AUDIO_CHUNK_TTL_SECONDS = 60 * 60
AUDIO_CHUNK_DIR = Path(tempfile.gettempdir()) / "nova-cinema-audio-chunks"
AUDIO_UPLOAD_LOCKS: dict[str, asyncio.Lock] = {}


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


def _validate_audio_content(filename: str, content: bytes) -> tuple[str, bytes]:
    suffix = Path(filename).suffix.lower()
    if suffix not in AUDIO_SUFFIXES:
        raise HTTPException(422, "Unsupported audio format")
    if suffix == ".mp3":
        try:
            content = _strip_leading_id3v2(content)
        except ValueError as error:
            raise HTTPException(422, "Invalid audio content") from error
    if not _looks_like_audio(suffix, content):
        raise HTTPException(422, "Invalid audio content")
    return suffix, content


def _transcode_large_audio(content: bytes, suffix: str) -> bytes:
    """Normalise large uploads to a stream-friendly 160 kbps MP3."""
    try:
        with tempfile.TemporaryDirectory(prefix="nova-audio-") as directory:
            root = Path(directory)
            source = root / f"source{suffix}"
            target = root / "output.mp3"
            source.write_bytes(content)
            subprocess.run(
                [
                    imageio_ffmpeg.get_ffmpeg_exe(),
                    "-y", "-v", "error", "-i", str(source),
                    "-map_metadata", "-1", "-vn", "-c:a", "libmp3lame",
                    "-b:a", "160k", "-ar", "44100",
                    "-fs", str(AUDIO_MAX_BYTES), str(target),
                ],
                check=True,
                capture_output=True,
                timeout=180,
            )
            if not target.is_file() or target.stat().st_size >= AUDIO_MAX_BYTES - CHUNK_BYTES:
                raise HTTPException(413, "Processed audio is too large")
            result = _strip_leading_id3v2(target.read_bytes())
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        raise HTTPException(422, "Audio could not be processed") from error
    if not _looks_like_mp3_frame(result):
        raise HTTPException(422, "Audio could not be processed")
    return result


def _store_audio_content(filename: str, content: bytes) -> str:
    if len(content) > AUDIO_MAX_BYTES:
        raise HTTPException(413, "Audio file is too large")
    suffix, content = _validate_audio_content(filename, content)
    if len(content) > AUDIO_TRANSCODE_THRESHOLD_BYTES:
        content = _transcode_large_audio(content, suffix)
        suffix = ".mp3"
    filename = f"{uuid.uuid4().hex}{suffix}"
    (UPLOAD_DIR / filename).write_bytes(content)
    return f"/uploads/{filename}"


async def save_audio_upload(file: UploadFile) -> str:
    """Validated melody upload (spec 4.7): no hardcoded audio files in the repo."""
    content = await _read_capped(file, AUDIO_MAX_BYTES, "Audio file is too large")
    return await asyncio.to_thread(_store_audio_content, file.filename or "", content)


def _purge_stale_audio_chunks() -> None:
    AUDIO_CHUNK_DIR.mkdir(parents=True, exist_ok=True)
    cutoff = time.time() - AUDIO_CHUNK_TTL_SECONDS
    for path in AUDIO_CHUNK_DIR.iterdir():
        try:
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
        except OSError:
            continue


def _append_audio_chunk(
    upload_id: str,
    chunk_index: int,
    total_chunks: int,
    total_size: int,
    safe_filename: str,
    content: bytes,
) -> tuple[Path, Path]:
    AUDIO_CHUNK_DIR.mkdir(parents=True, exist_ok=True)
    part = AUDIO_CHUNK_DIR / f"{upload_id}.part"
    metadata_path = AUDIO_CHUNK_DIR / f"{upload_id}.json"
    expected = {
        "filename": safe_filename,
        "total_chunks": total_chunks,
        "total_size": total_size,
    }
    if chunk_index == 0:
        _purge_stale_audio_chunks()
        part.unlink(missing_ok=True)
        metadata_path.unlink(missing_ok=True)
        part.write_bytes(content)
        metadata_path.write_text(json.dumps(expected), encoding="utf-8")
        return part, metadata_path

    if not part.is_file() or not metadata_path.is_file():
        raise HTTPException(409, "Audio chunks must be uploaded in order")
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise HTTPException(409, "Invalid audio upload session") from error
    if metadata != expected or part.stat().st_size != chunk_index * AUDIO_CHUNK_BYTES:
        raise HTTPException(409, "Audio chunks must be uploaded in order")
    with part.open("ab") as target:
        target.write(content)
    return part, metadata_path


async def save_audio_upload_chunk(
    *,
    upload_id: str,
    chunk_index: int,
    total_chunks: int,
    total_size: int,
    filename: str,
    file: UploadFile,
) -> dict[str, object]:
    """Assemble 1 MB requests below the tunnel's nginx body-size limit."""
    if AUDIO_UPLOAD_ID.fullmatch(upload_id) is None:
        raise HTTPException(422, "Invalid audio upload id")
    suffix = Path(filename).suffix.lower()
    if suffix not in AUDIO_SUFFIXES:
        raise HTTPException(422, "Unsupported audio format")
    if total_size <= 0:
        raise HTTPException(422, "Audio file is empty")
    if total_size > AUDIO_MAX_BYTES:
        raise HTTPException(413, "Audio file is too large")
    expected_total = (total_size + AUDIO_CHUNK_BYTES - 1) // AUDIO_CHUNK_BYTES
    if total_chunks != expected_total or not 0 <= chunk_index < total_chunks:
        raise HTTPException(422, "Invalid audio chunk metadata")
    expected_size = min(AUDIO_CHUNK_BYTES, total_size - chunk_index * AUDIO_CHUNK_BYTES)
    content = await _read_capped(file, expected_size, "Audio chunk is too large")
    if len(content) != expected_size:
        raise HTTPException(422, "Audio chunk has the wrong size")

    lock = AUDIO_UPLOAD_LOCKS.setdefault(upload_id, asyncio.Lock())
    async with lock:
        part, metadata_path = await asyncio.to_thread(
            _append_audio_chunk,
            upload_id,
            chunk_index,
            total_chunks,
            total_size,
            f"audio{suffix}",
            content,
        )
        if chunk_index < total_chunks - 1:
            return {"complete": False}

        try:
            if part.stat().st_size != total_size:
                raise HTTPException(422, "Audio upload is incomplete")
            assembled = await asyncio.to_thread(part.read_bytes)
            url = await asyncio.to_thread(_store_audio_content, f"audio{suffix}", assembled)
            return {"complete": True, "url": url}
        finally:
            part.unlink(missing_ok=True)
            metadata_path.unlink(missing_ok=True)
