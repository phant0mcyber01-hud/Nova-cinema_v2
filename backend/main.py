"""FastAPI application assembly: middleware, static files, lifespan, routers."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

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
    profile,
    public,
)
from backend.services.seed import seed


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
    application.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
    for module in (auth, public, catalog, booking, profile, admin, admin_catalog, admin_content):
        application.include_router(module.router)
    serve_built_frontend(application)
    return application


app = create_app()
