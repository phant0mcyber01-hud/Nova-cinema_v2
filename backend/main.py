"""FastAPI application assembly: middleware, static files, lifespan, routers."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.core.config import AUTO_CREATE_SCHEMA, CORS_ORIGINS, UPLOAD_DIR
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
    if AUTO_CREATE_SCHEMA:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with SessionLocal() as session:
            await seed(session)
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    application = FastAPI(title="Nova Cinema API", version="2.0", lifespan=lifespan)
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
    return application


app = create_app()
