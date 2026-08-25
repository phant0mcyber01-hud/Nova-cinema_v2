"""FastAPI application assembly: middleware, static files, lifespan, routers."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
import re

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import Headers
from starlette.types import Receive, Scope, Send

from backend.core.checks import log_configuration_warnings
from backend.core.config import AUTO_CREATE_SCHEMA, CORS_ORIGINS, PROJECT_ROOT, UPLOAD_DIR
from backend.core.db import Base, SessionLocal, engine
from backend.models import *  # noqa: F401,F403  -- registers every table on Base.metadata
from backend.api.routers import (
    admin,
    admin_catalog,
    admin_content,
    auth,
    booking,
    catalog,
    generic_booking,
    profile,
    public,
)
from backend.services.seed import seed


_AUDIO_SUFFIXES = {".mp3", ".ogg", ".m4a", ".wav"}
_OPEN_ENDED_RANGE = re.compile(r"bytes=(\d+)-", re.IGNORECASE)
_AUDIO_RANGE_BYTES = 128 * 1024


class StreamableAudioFileResponse(FileResponse):
    """Bound Chrome's open range so proxies cannot buffer the whole track."""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        range_header = Headers(scope=scope).get("range", "").strip()
        match = _OPEN_ENDED_RANGE.fullmatch(range_header)
        if match is None:
            await super().__call__(scope, receive, send)
            return

        digits = match.group(1)
        if len(digits) > 20:
            await PlainTextResponse("Malformed range header.", status_code=400)(scope, receive, send)
            return
        try:
            start = int(digits)
        except ValueError:
            await PlainTextResponse("Malformed range header.", status_code=400)(scope, receive, send)
            return
        bounded_range = f"bytes={start}-{start + _AUDIO_RANGE_BYTES - 1}".encode("ascii")
        bounded_scope = dict(scope)
        bounded_scope["headers"] = [
            (name, bounded_range if name.lower() == b"range" else value)
            for name, value in scope["headers"]
        ]
        await super().__call__(bounded_scope, receive, send)


class ImmutableUploadFiles(StaticFiles):
    """Static uploads have UUID names and never change at the same URL."""

    async def get_response(self, path: str, scope: dict):
        response = await super().get_response(path, scope)
        is_audio = Path(path).suffix.lower() in _AUDIO_SUFFIXES
        if isinstance(response, FileResponse) and is_audio:
            response = StreamableAudioFileResponse(
                response.path,
                status_code=response.status_code,
                headers=dict(response.headers),
                stat_result=response.stat_result,
            )
        if response.status_code in {200, 206, 304}:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        if is_audio:
            response.headers["X-Accel-Buffering"] = "no"
        return response


@asynccontextmanager
async def lifespan(_: FastAPI):
    log_configuration_warnings()
    if AUTO_CREATE_SCHEMA:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with SessionLocal() as session:
            await seed(session)
    yield
    await engine.dispose()


async def _overflowing_id(_: Request, __: OverflowError) -> JSONResponse:
    """An id too large for the database column identifies nothing.

    Without this it surfaced as a 500 from deep inside the driver: any caller
    could crash a request with /api/movies/99999999999999999999.
    """
    return JSONResponse(status_code=404, content={"detail": "Not found"})


def serve_built_frontend(application: FastAPI) -> None:
    """Serve the built Mini App from the API when a build is present.

    In Docker nginx does this. Running the cinema off one machine — a laptop
    behind a tunnel, a single small server — there is nothing to put in front,
    and two ports would mean two public addresses and a CORS rule between
    them. One origin removes all of it. Skipped entirely when the frontend has
    not been built, so development with `npm run dev` is unaffected.
    """
    dist = PROJECT_ROOT / "frontend" / "dist"
    index = dist / "index.html"
    if not index.is_file():
        return
    root = dist.resolve()

    @application.get("/{path:path}", include_in_schema=False)
    async def mini_app(path: str) -> FileResponse:
        # Registered last, so it only sees what no router claimed. An unknown
        # /api path is still a missing endpoint, not the Mini App.
        if path.startswith(("api/", "uploads/")):
            raise HTTPException(404, "Not found")
        candidate = (root / path).resolve()
        if path and candidate.is_file() and root in candidate.parents:
            return FileResponse(candidate)
        # Any other address is a route inside the app; React decides what it means.
        return FileResponse(index)


def create_app() -> FastAPI:
    application = FastAPI(title="Nova Cinema API", version="2.0", lifespan=lifespan)
    application.add_exception_handler(OverflowError, _overflowing_id)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    application.mount("/uploads", ImmutableUploadFiles(directory=UPLOAD_DIR), name="uploads")
    for module in (
        auth,
        public,
        catalog,
        generic_booking,
        booking,
        profile,
        admin,
        admin_catalog,
        admin_content,
    ):
        application.include_router(module.router)
    serve_built_frontend(application)
    return application


app = create_app()
