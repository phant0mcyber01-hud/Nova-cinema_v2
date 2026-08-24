"""Regression tests for fast, streamable cinema melodies."""
from __future__ import annotations

from tests.conftest import ADMIN_ID, auth_header, login


def _syncsafe(size: int) -> bytes:
    return bytes(((size >> 21) & 0x7F, (size >> 14) & 0x7F, (size >> 7) & 0x7F, size & 0x7F))


def _id3v2(payload: bytes, *, footer: bool = False) -> bytes:
    flags = 0x10 if footer else 0
    header = b"ID3" + bytes((4, 0, flags)) + _syncsafe(len(payload))
    trailer = b"3DI" + bytes((4, 0, flags)) + _syncsafe(len(payload)) if footer else b""
    return header + payload + trailer


# A frame-like MP3 prefix is sufficient for the upload signature validator.
MP3_AUDIO = b"\xff\xfb\x90\x64" + b"audio-frame" * 32


async def _upload(client, content: bytes):
    admin = await login(client, ADMIN_ID, "admin")
    return await client.post(
        "/api/admin/melodies/upload",
        files={"file": ("cinema.mp3", content, "audio/mpeg")},
        headers=auth_header(admin),
    )


async def test_mp3_upload_removes_complete_id3v2_tag_and_footer(client):
    response = await _upload(
        client,
        _id3v2(b"first-tag") + _id3v2(b"large-cover-art" * 32, footer=True) + MP3_AUDIO,
    )
    assert response.status_code == 200, response.text

    stored = await client.get(response.json()["url"])
    assert stored.status_code == 200
    assert stored.content == MP3_AUDIO, "the first response bytes must be playable MP3 frames"


async def test_mp3_upload_rejects_a_truncated_id3v2_tag(client):
    # The header promises 4 KiB of metadata, but the body ends immediately.
    malformed = b"ID3" + bytes((4, 0, 0)) + _syncsafe(4096) + b"short"
    response = await _upload(client, malformed)
    assert response.status_code == 422


async def test_mp3_upload_rejects_a_malformed_nested_id3v2_tag(client):
    malformed = b"ID3" + bytes((4, 0, 0)) + _syncsafe(4096) + b"short"
    response = await _upload(client, _id3v2(b"valid-outer-tag") + malformed)
    assert response.status_code == 422


async def test_mp3_upload_requires_a_valid_mpeg_frame_header(client):
    # Sync-like first bytes are insufficient: layer 00 is reserved by MPEG.
    response = await _upload(client, b"\xff\xe0\x00\x00" + b"not-audio" * 32)
    assert response.status_code == 422


async def test_uploaded_audio_is_immutable_cached_and_keeps_range_support(client):
    response = await _upload(client, MP3_AUDIO)
    assert response.status_code == 200, response.text
    url = response.json()["url"]

    whole = await client.get(url)
    assert whole.status_code == 200
    assert whole.headers["cache-control"] == "public, max-age=31536000, immutable"

    partial = await client.get(url, headers={"Range": "bytes=0-3"})
    assert partial.status_code == 206
    assert partial.content == MP3_AUDIO[:4]
    assert partial.headers["cache-control"] == "public, max-age=31536000, immutable"

    # Chrome asks for bytes=0-. Bound the first response so a public tunnel
    # cannot buffer the whole media file before forwarding the first frames.
    long_audio = MP3_AUDIO + b"next-frame" * 30_000
    long_response = await _upload(client, long_audio)
    long_url = long_response.json()["url"]
    streamed = await client.get(long_url, headers={"Range": "bytes=0-"})
    assert streamed.status_code == 206
    assert streamed.content == long_audio[:128 * 1024]
    assert streamed.headers["content-length"] == str(128 * 1024)
    assert streamed.headers["content-range"] == f"bytes 0-{128 * 1024 - 1}/{len(long_audio)}"
    assert streamed.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert streamed.headers["x-accel-buffering"] == "no"

    # Follow-up chunks stay the same size: on the measured tunnel 128 KiB
    # downloads faster than the ~3.2 seconds of 320 kbps audio it contains.
    continued = await client.get(long_url, headers={"Range": f"bytes={128 * 1024}-"})
    assert continued.status_code == 206
    assert continued.content == long_audio[128 * 1024:256 * 1024]
    assert continued.headers["content-length"] == str(128 * 1024)
    assert continued.headers["content-range"] == (
        f"bytes {128 * 1024}-{256 * 1024 - 1}/{len(long_audio)}"
    )

    malformed_range = await client.get(long_url, headers={"Range": f"bytes={'9' * 5000}-"})
    assert malformed_range.status_code in {400, 416}
