"""Music is gone from the product, so the API must not still offer it.

The client dropped the melody feature: it loaded the small box the cinema runs
on, Telegram blocks autoplay anyway, and it did not fit the room. The frontend
no longer has a player, so any endpoint left behind here is a public surface
serving a feature nobody can reach — including an unauthenticated upload path.

The stored rows are deliberately *not* dropped by a migration: the audio files
somebody uploaded stay on disk and in the table until the operator removes them
on purpose. This pins the API surface, not the data.
"""
from __future__ import annotations

import pathlib
import re

import pytest

from backend.main import create_app

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def routes() -> list[str]:
    return [getattr(route, "path", "") for route in create_app().routes]


def test_no_melody_endpoint_is_served(routes):
    offenders = [path for path in routes if "melod" in path.lower()]
    assert offenders == [], f"music was removed from the product, but the API still serves {offenders}"


def test_no_audio_upload_endpoint_survives(routes):
    offenders = [path for path in routes if re.search(r"audio|/upload/chunk", path, re.I)]
    assert offenders == [], f"the audio upload path outlived the feature: {offenders}"


def test_the_frontend_makes_no_audio_request():
    frontend = PROJECT_ROOT / "frontend" / "src"
    offenders = [
        str(path.relative_to(PROJECT_ROOT))
        for path in frontend.rglob("*.ts*")
        if re.search(r"melod|new Audio\(|audioPlayer|SoundToggle", path.read_text(encoding="utf-8"), re.I)
    ]
    assert offenders == [], f"music left the UI, but these files still reach for it: {offenders}"
