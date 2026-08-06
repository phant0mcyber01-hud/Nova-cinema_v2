from __future__ import annotations

import hashlib
import hmac
import asyncio
import json
import os
import re
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import AsyncGenerator
from urllib.parse import parse_qs, parse_qsl, urlparse

import jwt
import httpx
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, selectinload
from dotenv import load_dotenv


# Docker supplies its own environment.  For a direct local `uvicorn app:app`
# launch, load this project's .env before reading any configuration values.
# `override=False` deliberately keeps Docker/Windows environment variables authoritative.
load_dotenv(Path(__file__).resolve().with_name(".env"), override=False)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./nova-dev.db")
JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))
TELEGRAM_AUTH_MAX_AGE_SECONDS = int(os.getenv("TELEGRAM_AUTH_MAX_AGE_SECONDS", "86400"))
_admin_ids = os.getenv("ADMIN_TELEGRAM_IDS", "")
ADMIN_TELEGRAM_IDS = {int(value.strip()) for value in _admin_ids.split(",") if value.strip().isdigit()}
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")
OMDB_API_KEY = os.getenv("OMDB_API_KEY", "")
TRANSLATION_API_URL = os.getenv("TRANSLATION_API_URL", "https://libretranslate.com/translate")
TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_URL = "https://image.tmdb.org/t/p"
TIME_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"
DEMO_HALL_ROWS = 3
DEMO_HALL_COLS = 5
DEMO_HALL_SEATS = DEMO_HALL_ROWS * DEMO_HALL_COLS
engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
security = HTTPBearer(auto_error=False)


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


class Base(DeclarativeBase): pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    username: Mapped[str] = mapped_column(String(80), default="", index=True)
    first_name: Mapped[str] = mapped_column(String(80), default="")
    last_name: Mapped[str] = mapped_column(String(80), default="")
    phone: Mapped[str] = mapped_column(String(32), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    role: Mapped[str] = mapped_column(String(20), default="user")


class Movie(Base):
    __tablename__ = "movies"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    genre: Mapped[str] = mapped_column(String(120), index=True)
    description: Mapped[str] = mapped_column(Text)
    title_ru: Mapped[str] = mapped_column(String(255), default="")
    title_uz: Mapped[str] = mapped_column(String(255), default="")
    genre_ru: Mapped[str] = mapped_column(String(120), default="")
    genre_uz: Mapped[str] = mapped_column(String(120), default="")
    description_ru: Mapped[str] = mapped_column(Text, default="")
    description_uz: Mapped[str] = mapped_column(Text, default="")
    poster: Mapped[str] = mapped_column(String(1024))
    trailer_id: Mapped[str] = mapped_column(String(64))
    duration: Mapped[int] = mapped_column(Integer)
    age: Mapped[int] = mapped_column(Integer)
    year: Mapped[int] = mapped_column(Integer)
    country: Mapped[str] = mapped_column(String(255))
    director: Mapped[str] = mapped_column(String(255))
    cast_json: Mapped[str] = mapped_column(Text, default="[]")
    country_ru: Mapped[str] = mapped_column(String(255), default="")
    country_uz: Mapped[str] = mapped_column(String(255), default="")
    director_ru: Mapped[str] = mapped_column(String(255), default="")
    director_uz: Mapped[str] = mapped_column(String(255), default="")
    cast_json_ru: Mapped[str] = mapped_column(Text, default="[]")
    cast_json_uz: Mapped[str] = mapped_column(Text, default="[]")
    gallery_json: Mapped[str] = mapped_column(Text, default="[]")
    imdb: Mapped[float] = mapped_column(Float)
    kinopoisk: Mapped[float] = mapped_column(Float)
    internal_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_published: Mapped[bool] = mapped_column(default=True, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, index=True)
    sessions_json: Mapped[str] = mapped_column(Text, default="[]")
    ticket_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reviews: Mapped[list[Review]] = relationship(back_populates="movie", cascade="all, delete-orphan")


class Review(Base):
    __tablename__ = "reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    rating: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    approved: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    movie: Mapped[Movie] = relationship(back_populates="reviews")


class Booking(Base):
    __tablename__ = "bookings"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id"), index=True)
    session: Mapped[str] = mapped_column(String(30))
    show_date: Mapped[str] = mapped_column(String(10), default="", index=True)
    seats: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="confirmed", index=True)
    code: Mapped[str] = mapped_column(String(32), default="")
    total: Mapped[int] = mapped_column(Integer, default=0)
    first_name: Mapped[str] = mapped_column(String(80), default="")
    last_name: Mapped[str] = mapped_column(String(80), default="")
    phone: Mapped[str] = mapped_column(String(32), default="")
    telegram_username: Mapped[str] = mapped_column(String(80), default="")
    comment: Mapped[str] = mapped_column(Text, default="")
    proposed_session: Mapped[str] = mapped_column(String(30), default="")
    admin_note: Mapped[str] = mapped_column(Text, default="")
    uuid: Mapped[str] = mapped_column(String(36), default=lambda: str(uuid.uuid4()), unique=True, index=True)
    qr_token: Mapped[str] = mapped_column(String(64), default=lambda: uuid.uuid4().hex, unique=True, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class Favorite(Base):
    __tablename__ = "favorites"; __table_args__=(UniqueConstraint("user_id","movie_id",name="uq_favorite"),)
    id: Mapped[int] = mapped_column(primary_key=True); user_id: Mapped[int] = mapped_column(ForeignKey("users.id"),index=True); movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id"),index=True)

class UserNotification(Base):
    __tablename__ = "user_notifications"
    id: Mapped[int] = mapped_column(primary_key=True); user_id: Mapped[int] = mapped_column(ForeignKey("users.id"),index=True); type: Mapped[str] = mapped_column(String(40)); title: Mapped[str] = mapped_column(String(160)); message: Mapped[str] = mapped_column(Text); is_read: Mapped[bool] = mapped_column(default=False, index=True); created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))


class CinemaSettings(Base):
    __tablename__ = "cinema_settings"
    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    base_ticket_price: Mapped[int] = mapped_column(Integer, default=30000)


class SessionPrice(Base):
    __tablename__ = "session_prices"
    __table_args__ = (UniqueConstraint("movie_id", "show_date", "session", name="uq_session_price"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id"), index=True)
    show_date: Mapped[str] = mapped_column(String(10), index=True)
    session: Mapped[str] = mapped_column(String(30))
    ticket_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    seats_count: Mapped[int] = mapped_column(Integer, default=80)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)


class AdminNotification(Base):
    __tablename__ = "admin_notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id"), index=True)
    message: Mapped[str] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class SeatHold(Base):
    __tablename__ = "seat_holds"
    __table_args__ = (UniqueConstraint("movie_id", "show_date", "session", "seat", name="uq_seat_hold"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id"), index=True)
    show_date: Mapped[str] = mapped_column(String(10), index=True)
    session: Mapped[str] = mapped_column(String(30), index=True)
    seat: Mapped[str] = mapped_column(String(10), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


SEED_MOVIES = [
    {"title":"Дюна: Часть 2","genre":"Фантастика","duration":166,"age":12,"year":2024,"country":"США, Канада","director":"Дени Вильнёв","cast_json":json.dumps(["Тимоти Шаламе","Зендея","Ребекка Фергюсон"]),"poster":"https://image.tmdb.org/t/p/w780/1pdfLvkbY9ohJlCjQH2CZjjYVvJ.jpg","trailer_id":"Way9Dexny3w","gallery_json":json.dumps(["https://image.tmdb.org/t/p/w1280/8b8R8l88Qje9dn9OE8PY05Nxl1X.jpg","https://image.tmdb.org/t/p/w1280/xOMo8BRK7PfcJv9JCnx7s5hj0PX.jpg"]),"imdb":8.6,"kinopoisk":8.7,"description":"Пол Атрейдес объединяется с Чани и фременами, чтобы защитить Арракис.","sessions_json":json.dumps(["12:00","15:30","19:00","22:15"])},
    {"title":"Кунг-фу Панда 4","genre":"Мультфильм","duration":94,"age":6,"year":2024,"country":"США, Китай","director":"Майк Митчелл","cast_json":json.dumps(["Джек Блэк","Аквафина","Виола Дэвис"]),"poster":"https://image.tmdb.org/t/p/w780/kDp1vUBnMpe8ak4rjgl3cLELqjU.jpg","trailer_id":"_inKs4eeHiI","gallery_json":json.dumps(["https://image.tmdb.org/t/p/w1280/kDp1vUBnMpe8ak4rjgl3cLELqjU.jpg"]),"imdb":6.3,"kinopoisk":7.5,"description":"По ищет преемника и встречает ловкую лисицу Чжэнь.","sessions_json":json.dumps(["10:00","13:15","16:30"])},
    {"title":"Оппенгеймер","genre":"Драма","duration":180,"age":18,"year":2023,"country":"США, Великобритания","director":"Кристофер Нолан","cast_json":json.dumps(["Киллиан Мёрфи","Эмили Блант","Мэтт Дэймон"]),"poster":"https://image.tmdb.org/t/p/w780/8Gxv8gSFCU0XGDykEGv7zR1n2ua.jpg","trailer_id":"uYPbbksJxIg","gallery_json":json.dumps(["https://image.tmdb.org/t/p/w1280/8Gxv8gSFCU0XGDykEGv7zR1n2ua.jpg"]),"imdb":8.6,"kinopoisk":8.2,"description":"История физика Роберта Оппенгеймера и создания атомной бомбы.","sessions_json":json.dumps(["14:00","17:30","21:00"])},
]


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session: yield session


async def seed(session: AsyncSession) -> None:
    if (await session.scalar(select(Movie.id).limit(1))) is None:
        session.add_all([Movie(**item) for item in SEED_MOVIES]); await session.commit()
    if await session.get(CinemaSettings, 1) is None:
        session.add(CinemaSettings(id=1, base_ticket_price=30000)); await session.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if os.getenv("AUTO_CREATE_SCHEMA", "false").lower() == "true":
        async with engine.begin() as connection: await connection.run_sync(Base.metadata.create_all)
        async with SessionLocal() as session: await seed(session)
    yield
    await engine.dispose()


app = FastAPI(title="Nova Cinema API", version="2.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[value for value in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")], allow_methods=["GET","POST","PATCH","DELETE"], allow_headers=["Authorization","Content-Type"])
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

class TelegramAuthIn(BaseModel): init_data: str = Field(min_length=10)
class ReviewIn(BaseModel): rating: int = Field(ge=1, le=5); text: str = Field(min_length=3, max_length=1000)
class HoldIn(BaseModel): movie_id: int; show_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$"); session: str = Field(pattern=TIME_PATTERN); seats: list[str] = Field(min_length=1, max_length=6)
class BookingConfirmIn(HoldIn):
    first_name: str = Field(min_length=2, max_length=80)
    last_name: str = Field(min_length=2, max_length=80)
    phone: str = Field(pattern=r"^\+?[0-9\s()\-]{7,32}$")
    telegram_username: str = Field(default="", max_length=80, pattern=r"^$|^@?[A-Za-z0-9_]{5,32}$")
    comment: str = Field(default="", max_length=1000)
class BookingStatusIn(BaseModel): status: str = Field(pattern=r"^(pending|confirmed|cancelled|completed)$")
class BookingDecisionIn(BaseModel):
    action: str = Field(pattern=r"^(confirm|decline|propose)$")
    reason: str = Field(default="", max_length=500)
    proposed_session: str = Field(default="", max_length=30)

    @field_validator("proposed_session")
    @classmethod
    def validate_proposed_session(cls, value: str) -> str:
        value = value.strip()
        if value and not re.fullmatch(TIME_PATTERN, value):
            raise ValueError("Invalid proposed time")
        return value

class BookingProposalIn(BaseModel): action: str = Field(pattern=r"^(accept|decline)$")
class BasePriceIn(BaseModel): base_ticket_price: int = Field(ge=1, le=10_000_000)
class ProfileIn(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(default="", max_length=80)
    phone: str = Field(default="", max_length=32)

    @field_validator("first_name")
    @classmethod
    def validate_first_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("First name is required")
        return value

    @field_validator("last_name")
    @classmethod
    def normalize_last_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        value = value.strip()
        if not value:
            return ""
        if not re.fullmatch(r"\+?[0-9\s()\-]{7,32}", value):
            raise ValueError("Invalid phone number")
        normalized = "+" + "".join(character for character in value if character.isdigit())
        if not 8 <= len(normalized) <= 16:
            raise ValueError("Invalid phone number")
        return normalized
class MovieIn(BaseModel):
    title: str = Field(min_length=1,max_length=255); genre: str = Field(min_length=1,max_length=120); description: str; poster: str; trailer_id: str; duration: int = Field(ge=1); age: int = Field(ge=0,le=21); year: int = Field(ge=1888,le=2100); country: str; director: str; cast: list[str] = Field(default_factory=list); gallery: list[str] = Field(default_factory=list); imdb: float = Field(ge=0,le=10); kinopoisk: float = Field(ge=0,le=10); internal_rating: float | None = Field(default=None,ge=0,le=10); ticket_price: int | None = Field(default=None,ge=1); is_published: bool = True; sort_order: int = 0

    @field_validator("trailer_id")
    @classmethod
    def normalize_trailer(cls, value: str) -> str:
        return youtube_video_id(value)
class MovieLookupIn(BaseModel): title: str = Field(min_length=1, max_length=255)
class SessionIn(BaseModel): movie_id: int; show_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$"); session: str = Field(min_length=4,max_length=30); ticket_price: int | None = Field(default=None,ge=1); seats_count: int = Field(default=DEMO_HALL_SEATS, ge=1, le=200); status: str = Field(default="active", pattern=r"^(active|inactive|cancelled)$")

def telegram_user(init_data: str) -> dict[str, object]:
    token = os.getenv("BOT_TOKEN")
    if token is None: raise HTTPException(503, "Telegram Auth is not configured")
    values = dict(parse_qsl(init_data, keep_blank_values=True)); received = values.pop("hash", "")
    check = "\n".join(f"{key}={values[key]}" for key in sorted(values)); secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest(); expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not received or not hmac.compare_digest(expected, received): raise HTTPException(401, "Invalid Telegram signature")
    try:
        auth_date = datetime.fromtimestamp(int(values["auth_date"]), timezone.utc)
    except (KeyError, ValueError) as error:
        raise HTTPException(401, "Telegram auth_date missing") from error
    if datetime.now(timezone.utc) - auth_date > timedelta(seconds=TELEGRAM_AUTH_MAX_AGE_SECONDS):
        raise HTTPException(401, "Telegram initData expired")
    try: return json.loads(str(values["user"]))
    except (KeyError, json.JSONDecodeError) as error: raise HTTPException(401, "Telegram user missing") from error

def issue_token(user: User) -> str:
    if not JWT_SECRET: raise HTTPException(503, "JWT_SECRET is not configured")
    return jwt.encode({"sub":str(user.id),"role":user.role,"exp":datetime.now(timezone.utc)+timedelta(hours=12)}, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(security), session: AsyncSession = Depends(get_db)) -> User:
    if credentials is None or not JWT_SECRET: raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    try: payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM]); user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as error: raise HTTPException(401, "Invalid access token") from error
    user = await session.get(User, user_id)
    if user is None: raise HTTPException(401, "User not found")
    expected_role = "admin" if user.telegram_id in ADMIN_TELEGRAM_IDS else "user"
    if user.role != expected_role:
        user.role = expected_role
        await session.commit()
        await session.refresh(user)
    return user

async def admin_required(user: User = Depends(current_user)) -> User:
    if user.telegram_id not in ADMIN_TELEGRAM_IDS or user.role != "admin": raise HTTPException(403, "Admin role required")
    return user

def normalize_language(language: str) -> str:
    return "uz" if language.lower().startswith("uz") else "ru"


def detect_content_language(values: list[str]) -> str:
    text = " ".join(values)
    return "ru" if re.search(r"[А-Яа-яЁё]", text) else "uz"


async def translate_text(value: str, source: str, target: str) -> tuple[str, bool]:
    text = value.strip()
    if not text or source == target:
        return text, False
    if not TRANSLATION_API_URL:
        return text, True
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                TRANSLATION_API_URL,
                json={"q": text, "source": source, "target": target, "format": "text"},
            )
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError):
        return text, True
    translated = data.get("translatedText") if isinstance(data, dict) else None
    return (str(translated).strip() or text, False) if translated else (text, True)


async def localize_movie_payload(payload: MovieIn) -> tuple[dict[str, object], bool]:
    source = detect_content_language([payload.title, payload.genre, payload.description, payload.country, payload.director, *payload.cast])
    target = "uz" if source == "ru" else "ru"
    warning = False
    translated: dict[str, str] = {}
    for field in ("title", "genre", "description", "country", "director"):
        translated[field], failed = await translate_text(str(getattr(payload, field)), source, target)
        warning = warning or failed
    translated_cast: list[str] = []
    for item in payload.cast:
        value, failed = await translate_text(item, source, target)
        translated_cast.append(value)
        warning = warning or failed
    original = payload.model_dump(exclude={"cast", "gallery"})
    original.update({"cast_json": json.dumps(payload.cast), "gallery_json": json.dumps(payload.gallery)})
    if source == "ru":
        original.update({
            "title": payload.title,
            "genre": payload.genre,
            "description": payload.description,
            "country": payload.country,
            "director": payload.director,
            "cast_json": json.dumps(payload.cast),
            "title_ru": payload.title,
            "genre_ru": payload.genre,
            "description_ru": payload.description,
            "country_ru": payload.country,
            "director_ru": payload.director,
            "cast_json_ru": json.dumps(payload.cast),
            "title_uz": translated["title"],
            "genre_uz": translated["genre"],
            "description_uz": translated["description"],
            "country_uz": translated["country"],
            "director_uz": translated["director"],
            "cast_json_uz": json.dumps(translated_cast),
        })
    else:
        original.update({
            "title": translated["title"],
            "genre": translated["genre"],
            "description": translated["description"],
            "country": translated["country"],
            "director": translated["director"],
            "cast_json": json.dumps(translated_cast),
            "title_ru": translated["title"],
            "genre_ru": translated["genre"],
            "description_ru": translated["description"],
            "country_ru": translated["country"],
            "director_ru": translated["director"],
            "cast_json_ru": json.dumps(translated_cast),
            "title_uz": payload.title,
            "genre_uz": payload.genre,
            "description_uz": payload.description,
            "country_uz": payload.country,
            "director_uz": payload.director,
            "cast_json_uz": json.dumps(payload.cast),
        })
    return original, warning


def localized_movie_text(movie: Movie, language: str) -> dict[str, object]:
    lang = normalize_language(language)
    if lang == "uz":
        return {
            "title": movie.title_uz or movie.title,
            "genre": movie.genre_uz or movie.genre,
            "description": movie.description_uz or movie.description,
            "country": movie.country_uz or movie.country,
            "director": movie.director_uz or movie.director,
            "cast": json.loads(movie.cast_json_uz or movie.cast_json),
        }
    return {
        "title": movie.title_ru or movie.title,
        "genre": movie.genre_ru or movie.genre,
        "description": movie.description_ru or movie.description,
        "country": movie.country_ru or movie.country,
        "director": movie.director_ru or movie.director,
        "cast": json.loads(movie.cast_json_ru or movie.cast_json),
    }


def serialize_movie(movie: Movie, reviews: list[Review] | None = None, language: str = "ru") -> dict[str, object]:
    items = [review for review in (reviews if reviews is not None else movie.reviews) if review.approved]
    user_rating = round(sum(item.rating for item in items)/len(items),1) if items else movie.internal_rating
    text = localized_movie_text(movie, language)
    return {"id":movie.id,"title":text["title"],"genre":text["genre"],"description":text["description"],"poster":movie.poster,"trailer_id":movie.trailer_id,"duration":movie.duration,"age":movie.age,"year":movie.year,"country":text["country"],"director":text["director"],"cast":text["cast"],"gallery":json.loads(movie.gallery_json),"imdb":movie.imdb,"kinopoisk":movie.kinopoisk,"sessions":json.loads(movie.sessions_json),"user_rating":user_rating,"rating":user_rating or 0,"internal_rating":movie.internal_rating,"ticket_price":movie.ticket_price,"is_published":movie.is_published,"sort_order":movie.sort_order}

def tmdb_image(path: str | None, size: str = "w780") -> str:
    return f"{TMDB_IMAGE_URL}/{size}{path}" if path else ""

def age_from_releases(releases: dict[str, object]) -> int:
    results = releases.get("results", []) if isinstance(releases, dict) else []
    if not isinstance(results, list): return 12
    certificates: list[str] = []
    for country in ("RU", "UZ", "US"):
        for item in results:
            if not isinstance(item, dict) or item.get("iso_3166_1") != country: continue
            items = item.get("release_dates", [])
            if isinstance(items, list): certificates.extend(str(row.get("certification", "")) for row in items if isinstance(row, dict))
    text = " ".join(certificates).upper()
    if "18" in text or "NC-17" in text or "R" in text: return 18
    if "16" in text: return 16
    if "13" in text or "PG-13" in text: return 13
    if "12" in text: return 12
    if "6" in text or "PG" in text: return 6
    return 12

def youtube_from_videos(videos: dict[str, object]) -> str:
    results = videos.get("results", []) if isinstance(videos, dict) else []
    if not isinstance(results, list): return ""
    youtube = [item for item in results if isinstance(item, dict) and item.get("site") == "YouTube"]
    trailers = [item for item in youtube if str(item.get("type", "")).lower() == "trailer"]
    official = [item for item in trailers if item.get("official")]
    choice = (official or trailers or youtube or [{}])[0]
    return str(choice.get("key", ""))

def rating_from_omdb(value: str) -> float:
    try: return round(float(value), 1)
    except ValueError: return 0

async def fetch_json(client: httpx.AsyncClient, url: str, params: dict[str, object]) -> dict[str, object]:
    try:
        response = await client.get(url, params=params)
    except httpx.HTTPError as error:
        raise HTTPException(502, "Movie API is unavailable") from error
    if response.status_code == 401: raise HTTPException(503, "Movie API key is invalid")
    if response.status_code == 404: raise HTTPException(404, "Movie not found")
    if response.status_code >= 400: raise HTTPException(502, "Movie API request failed")
    data = response.json()
    return data if isinstance(data, dict) else {}

async def lookup_movie_payload(title: str) -> dict[str, object]:
    if not TMDB_API_KEY: raise HTTPException(503, "TMDB_API_KEY is not configured")
    async with httpx.AsyncClient(timeout=12) as client:
        search = await fetch_json(client, f"{TMDB_BASE_URL}/search/movie", {"api_key": TMDB_API_KEY, "query": title, "language": "ru-RU", "include_adult": "false"})
        results = search.get("results", [])
        if not isinstance(results, list) or not results: raise HTTPException(404, "Movie not found")
        movie_id = results[0].get("id")
        if not movie_id: raise HTTPException(404, "Movie not found")
        details = await fetch_json(client, f"{TMDB_BASE_URL}/movie/{movie_id}", {"api_key": TMDB_API_KEY, "language": "ru-RU", "append_to_response": "credits,images,videos,external_ids,release_dates", "include_image_language": "ru,en,null"})
        imdb_id = str((details.get("external_ids") or {}).get("imdb_id") or "")
        omdb: dict[str, object] = {}
        if OMDB_API_KEY and imdb_id:
            omdb = await fetch_json(client, "https://www.omdbapi.com/", {"apikey": OMDB_API_KEY, "i": imdb_id, "plot": "full"})
    credits = details.get("credits") if isinstance(details.get("credits"), dict) else {}
    crew = credits.get("crew", []) if isinstance(credits, dict) else []
    cast_items = credits.get("cast", []) if isinstance(credits, dict) else []
    director = next((str(item.get("name", "")) for item in crew if isinstance(item, dict) and item.get("job") == "Director"), "")
    cast = [str(item.get("name", "")) for item in cast_items[:8] if isinstance(item, dict) and item.get("name")]
    countries = details.get("production_countries", [])
    genres = details.get("genres", [])
    images = details.get("images") if isinstance(details.get("images"), dict) else {}
    backdrops = images.get("backdrops", []) if isinstance(images, dict) else []
    posters = images.get("posters", []) if isinstance(images, dict) else []
    gallery_paths = [item.get("file_path") for item in [*backdrops[:6], *posters[:3]] if isinstance(item, dict) and item.get("file_path")]
    release_date = str(details.get("release_date", ""))
    description = str(details.get("overview") or omdb.get("Plot") or "")
    imdb = rating_from_omdb(str(omdb.get("imdbRating", "0")))
    tmdb_rating = round(float(details.get("vote_average") or 0), 1)
    return {
        "title": str(details.get("title") or details.get("original_title") or title),
        "description": description,
        "genre": ", ".join(str(item.get("name", "")) for item in genres if isinstance(item, dict) and item.get("name")),
        "country": ", ".join(str(item.get("name", "")) for item in countries if isinstance(item, dict) and item.get("name")),
        "year": int(release_date[:4]) if release_date[:4].isdigit() else datetime.now(timezone.utc).year,
        "duration": int(details.get("runtime") or 90),
        "age": age_from_releases(details.get("release_dates") if isinstance(details.get("release_dates"), dict) else {}),
        "director": director,
        "cast": cast,
        "imdb": imdb,
        "kinopoisk": 0,
        "internal_rating": tmdb_rating or None,
        "trailer_id": youtube_from_videos(details.get("videos") if isinstance(details.get("videos"), dict) else {}),
        "poster": tmdb_image(str(details.get("poster_path") or ""), "w780"),
        "gallery": [tmdb_image(str(path), "w1280") for path in gallery_paths],
        "ticket_price": None,
        "is_published": True,
        "sort_order": 0,
    }

@app.post("/api/auth/telegram")
async def auth(payload: TelegramAuthIn, session: AsyncSession = Depends(get_db)) -> dict[str, object]:
    data = telegram_user(payload.init_data); telegram_id = int(data["id"]); user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
    expected_role = "admin" if telegram_id in ADMIN_TELEGRAM_IDS else "user"
    username = str(data.get("username", ""))
    if user is None:
        user = User(telegram_id=telegram_id, name=str(data.get("first_name", "Гость")), username=username, role=expected_role); session.add(user); await session.commit(); await session.refresh(user)
    elif user.role != expected_role or user.username != username:
        user.role = expected_role; user.username = username; await session.commit()
    return {"access_token":issue_token(user),"token_type":"bearer","user":{"id":user.id,"name":user.name,"role":user.role}}

@app.get("/api/movies")
async def movies(lang: str = "ru", session: AsyncSession = Depends(get_db)) -> list[dict[str, object]]:
    result = await session.scalars(select(Movie).options(selectinload(Movie.reviews)).where(Movie.is_published == True).order_by(Movie.sort_order, Movie.id)); return [serialize_movie(movie, language=lang) for movie in result]

@app.get("/api/movies/{movie_id}")
async def movie_detail(movie_id: int, lang: str = "ru", session: AsyncSession = Depends(get_db)) -> dict[str, object]:
    movie = await session.scalar(select(Movie).options(selectinload(Movie.reviews)).where(Movie.id == movie_id))
    if movie is None or not movie.is_published: raise HTTPException(404, "Movie not found")
    data = serialize_movie(movie, language=lang); data["reviews"] = [{"rating":review.rating,"text":review.text,"created_at":review.created_at,"user_name":"Зритель"} for review in movie.reviews if review.approved]
    similar = await session.scalars(select(Movie).where(Movie.id != movie_id, Movie.is_published == True).order_by(Movie.sort_order, Movie.id).limit(2)); data["similar_movies"] = [serialize_movie(item, [], lang) for item in similar]
    return data

@app.get("/api/movies/{movie_id}/sessions")
async def movie_sessions(movie_id: int, show_date: str, session: AsyncSession = Depends(get_db)) -> dict[str, object]:
    movie = await session.get(Movie, movie_id)
    if movie is None or not movie.is_published: raise HTTPException(404, "Movie not found")
    base_sessions = set(json.loads(movie.sessions_json))
    overrides = await session.scalars(select(SessionPrice).where(SessionPrice.movie_id == movie_id, SessionPrice.show_date == show_date, SessionPrice.status == "active"))
    return {"movie_id": movie_id, "show_date": show_date, "sessions": sorted(base_sessions | {item.session for item in overrides})}

@app.post("/api/movies/{movie_id}/reviews")
async def create_review(movie_id: int, payload: ReviewIn, user: User = Depends(current_user), session: AsyncSession = Depends(get_db)) -> dict[str,str]:
    seen = await session.scalar(select(Booking.id).where(Booking.user_id == user.id, Booking.movie_id == movie_id, Booking.status == "completed"))
    if seen is None: raise HTTPException(403, "Review is available after viewing")
    session.add(Review(movie_id=movie_id,user_id=user.id,rating=payload.rating,text=payload.text.strip())); await session.commit(); return {"status":"published"}

@app.get("/api/profile")
async def profile(user:User=Depends(current_user),session:AsyncSession=Depends(get_db))->dict[str,object]:
    count=await session.scalar(select(func.count()).select_from(Booking).where(Booking.user_id==user.id)) or 0
    return {"first_name":user.first_name or user.name,"last_name":user.last_name,"phone":user.phone,"telegram_id":user.telegram_id,"created_at":user.created_at,"bookings":count}
@app.patch("/api/profile")
async def edit_profile(payload:ProfileIn,user:User=Depends(current_user),session:AsyncSession=Depends(get_db))->dict[str,str]:
    user.first_name=payload.first_name.strip();user.last_name=payload.last_name.strip();user.phone=payload.phone.strip();user.name=user.first_name;await session.commit();return {"status":"updated"}
@app.get("/api/profile/bookings")
async def profile_bookings(lang:str="ru",user:User=Depends(current_user),session:AsyncSession=Depends(get_db))->list[dict[str,object]]:
    rows=await session.execute(select(Booking,Movie).join(Movie,Booking.movie_id==Movie.id).where(Booking.user_id==user.id).order_by(Booking.id.desc()));return [{"id":b.id,"uuid":b.uuid,"qr_token":b.qr_token,"qr_valid":b.status in ("confirmed","completed"),"movie":localized_movie_text(m,lang)["title"],"poster":m.poster,"description":localized_movie_text(m,lang)["description"],"trailer_id":m.trailer_id,"show_date":b.show_date,"session":b.session,"seats":b.seats,"total":b.total,"status":b.status,"phone":b.phone,"telegram_username":b.telegram_username,"comment":b.comment,"proposed_session":b.proposed_session,"admin_note":b.admin_note} for b,m in rows]
@app.get("/api/profile/bookings/{booking_id}")
async def profile_booking(booking_id:int,lang:str="ru",user:User=Depends(current_user),session:AsyncSession=Depends(get_db))->dict[str,object]:
    rows=await session.execute(select(Booking,Movie).join(Movie,Booking.movie_id==Movie.id).where(Booking.id==booking_id,Booking.user_id==user.id));item=rows.first()
    if item is None:raise HTTPException(404,"Booking not found")
    b,m=item;text=localized_movie_text(m,lang);return {"id":b.id,"uuid":b.uuid,"qr_token":b.qr_token,"qr_valid":b.status in ("confirmed","completed"),"movie":text["title"],"poster":m.poster,"description":text["description"],"trailer_id":m.trailer_id,"show_date":b.show_date,"session":b.session,"seats":b.seats,"total":b.total,"status":b.status,"phone":b.phone,"telegram_username":b.telegram_username,"comment":b.comment,"proposed_session":b.proposed_session,"admin_note":b.admin_note}
@app.get("/api/profile/favorites")
async def favorites(lang:str="ru",user:User=Depends(current_user),session:AsyncSession=Depends(get_db))->list[dict[str,object]]:
    rows=await session.scalars(select(Movie).options(selectinload(Movie.reviews)).join(Favorite,Favorite.movie_id==Movie.id).where(Favorite.user_id==user.id, Movie.is_published == True));return [serialize_movie(item, language=lang) for item in rows]
@app.post("/api/profile/favorites/{movie_id}")
async def add_favorite(movie_id:int,user:User=Depends(current_user),session:AsyncSession=Depends(get_db))->dict[str,str]:
    if await session.get(Movie,movie_id) is None:raise HTTPException(404,"Movie not found")
    if await session.scalar(select(Favorite).where(Favorite.user_id==user.id,Favorite.movie_id==movie_id)) is None:session.add(Favorite(user_id=user.id,movie_id=movie_id));await session.commit()
    return {"status":"added"}
@app.delete("/api/profile/favorites/{movie_id}")
async def remove_favorite(movie_id:int,user:User=Depends(current_user),session:AsyncSession=Depends(get_db))->dict[str,str]:
    item=await session.scalar(select(Favorite).where(Favorite.user_id==user.id,Favorite.movie_id==movie_id));
    if item:await session.delete(item);await session.commit()
    return {"status":"removed"}
@app.get("/api/profile/notifications")
async def profile_notifications(user:User=Depends(current_user),session:AsyncSession=Depends(get_db))->list[dict[str,object]]:
    rows=await session.scalars(select(UserNotification).where(UserNotification.user_id==user.id).order_by(UserNotification.id.desc()));return [{"id":n.id,"type":n.type,"title":n.title,"message":n.message,"is_read":n.is_read,"created_at":n.created_at} for n in rows]
@app.patch("/api/profile/notifications/{notification_id}/read")
async def read_profile_notification(notification_id:int,user:User=Depends(current_user),session:AsyncSession=Depends(get_db))->dict[str,bool]:
    n=await session.scalar(select(UserNotification).where(UserNotification.id==notification_id,UserNotification.user_id==user.id));
    if n is None:raise HTTPException(404,"Notification not found")
    n.is_read=True;await session.commit();return {"is_read":True}

async def ensure_public_session(session: AsyncSession, movie_id: int, show_date: str, session_time: str) -> Movie:
    movie = await session.get(Movie, movie_id)
    if movie is None or not movie.is_published: raise HTTPException(404, "Movie not found")
    if session_time in set(json.loads(movie.sessions_json)): return movie
    exists = await session.scalar(select(SessionPrice.id).where(SessionPrice.movie_id == movie_id, SessionPrice.show_date == show_date, SessionPrice.session == session_time, SessionPrice.status == "active"))
    if exists is None and not re.fullmatch(TIME_PATTERN, session_time): raise HTTPException(404, "Session not found")
    return movie

def hall_columns(seats_count: int) -> int:
    """Keep the 3x5 demo hall while producing usable grids for larger halls."""
    if seats_count <= 30:
        return 5
    if seats_count <= 80:
        return 10
    return 12


def valid_seat(seat: str, seats_count: int = DEMO_HALL_SEATS) -> bool:
    try:
        row, column = (int(value) for value in seat.split("-", 1))
        columns = hall_columns(seats_count)
        return 1 <= column <= columns and 1 <= ((row - 1) * columns + column) <= seats_count
    except ValueError: return False

async def ticket_price(session: AsyncSession, movie_id: int, show_date: str, session_time: str) -> int:
    session_price = await session.scalar(select(SessionPrice.ticket_price).where(SessionPrice.movie_id == movie_id, SessionPrice.show_date == show_date, SessionPrice.session == session_time, SessionPrice.status == "active"))
    if session_price and session_price > 0: return session_price
    movie_price = await session.scalar(select(Movie.ticket_price).where(Movie.id == movie_id))
    if movie_price and movie_price > 0: return movie_price
    settings = await session.get(CinemaSettings, 1)
    return settings.base_ticket_price if settings and settings.base_ticket_price > 0 else 30000


async def send_telegram_message(telegram_id: int, message: str) -> None:
    token = os.getenv("BOT_TOKEN")
    if not token:
        return
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            await client.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": telegram_id, "text": message})
    except httpx.HTTPError:
        return


def user_booking_notification(booking: Booking, title: str, message: str) -> UserNotification:
    return UserNotification(user_id=booking.user_id, type="booking_status", title=title, message=message)

async def session_seats_count(session: AsyncSession, movie_id: int, show_date: str, session_time: str) -> int:
    seats_count = await session.scalar(select(SessionPrice.seats_count).where(SessionPrice.movie_id == movie_id, SessionPrice.show_date == show_date, SessionPrice.session == session_time, SessionPrice.status == "active"))
    return seats_count if seats_count and seats_count > 0 else DEMO_HALL_SEATS

@app.get("/api/sessions/{movie_id}/seats")
async def session_seats(movie_id: int, show_date: str, session_time: str, session: AsyncSession = Depends(get_db)) -> dict[str, object]:
    await ensure_public_session(session, movie_id, show_date, session_time)
    now = datetime.now(timezone.utc); await session.execute(SeatHold.__table__.delete().where(SeatHold.expires_at < now)); await session.commit()
    bookings = await session.scalars(select(Booking).where(Booking.movie_id == movie_id, Booking.show_date == show_date, Booking.session == session_time, Booking.status.in_(["pending", "confirmed", "completed"])))
    holds = await session.scalars(select(SeatHold).where(SeatHold.movie_id == movie_id, SeatHold.show_date == show_date, SeatHold.session == session_time))
    taken = {seat for booking in bookings for seat in booking.seats.split(",")} | {hold.seat for hold in holds}
    seats_count = await session_seats_count(session, movie_id, show_date, session_time)
    columns = hall_columns(seats_count)
    return {"rows": (seats_count + columns - 1) // columns, "cols": columns, "seats_count": seats_count, "price": await ticket_price(session, movie_id, show_date, session_time), "taken": sorted(taken)}

@app.post("/api/holds")
async def hold_seats(payload: HoldIn, user: User = Depends(current_user), session: AsyncSession = Depends(get_db)) -> dict[str, object]:
    await ensure_public_session(session, payload.movie_id, payload.show_date, payload.session)
    seats_count = await session_seats_count(session, payload.movie_id, payload.show_date, payload.session)
    if len(set(payload.seats)) != len(payload.seats) or not all(valid_seat(seat, seats_count) for seat in payload.seats): raise HTTPException(422, "Invalid seats")
    now = datetime.now(timezone.utc); await session.execute(SeatHold.__table__.delete().where(SeatHold.expires_at < now))
    existing = await session.scalars(select(SeatHold).where(SeatHold.movie_id == payload.movie_id, SeatHold.show_date == payload.show_date, SeatHold.session == payload.session, SeatHold.seat.in_(payload.seats), SeatHold.user_id != user.id).with_for_update())
    if list(existing): raise HTTPException(409, "Seat is temporarily held")
    bookings = await session.scalars(select(Booking).where(Booking.movie_id == payload.movie_id, Booking.show_date == payload.show_date, Booking.session == payload.session, Booking.status.in_(["pending", "confirmed", "completed"])))
    if set(payload.seats).intersection({seat for item in bookings for seat in item.seats.split(",")}): raise HTTPException(409, "Seat is already booked")
    await session.execute(SeatHold.__table__.delete().where(SeatHold.movie_id == payload.movie_id, SeatHold.show_date == payload.show_date, SeatHold.session == payload.session, SeatHold.user_id == user.id))
    expires = now + timedelta(minutes=10); session.add_all([SeatHold(movie_id=payload.movie_id, show_date=payload.show_date, session=payload.session, seat=seat, user_id=user.id, expires_at=expires) for seat in payload.seats]); await session.commit()
    return {"expires_at":expires,"seats":payload.seats,"total":len(payload.seats)*await ticket_price(session, payload.movie_id, payload.show_date, payload.session)}

@app.post("/api/bookings/confirm")
async def confirm_booking(payload: BookingConfirmIn, user: User = Depends(current_user), session: AsyncSession = Depends(get_db)) -> dict[str, object]:
    await ensure_public_session(session, payload.movie_id, payload.show_date, payload.session)
    holds = await session.scalars(select(SeatHold).where(SeatHold.movie_id == payload.movie_id, SeatHold.show_date == payload.show_date, SeatHold.session == payload.session, SeatHold.user_id == user.id, SeatHold.seat.in_(payload.seats), SeatHold.expires_at > datetime.now(timezone.utc)).with_for_update())
    if len(list(holds)) != len(payload.seats): raise HTTPException(409, "Hold expired")
    phone = "+" + "".join(char for char in payload.phone if char.isdigit())
    if len(phone) < 8 or len(phone) > 16: raise HTTPException(422, "Invalid phone number")
    username = payload.telegram_username.strip().lstrip("@") or user.username
    code = str(user.telegram_id); booking = Booking(user_id=user.id,movie_id=payload.movie_id,show_date=payload.show_date,session=payload.session,seats=",".join(payload.seats),code=code,total=len(payload.seats)*await ticket_price(session, payload.movie_id, payload.show_date, payload.session),status="pending",first_name=payload.first_name.strip(),last_name=payload.last_name.strip(),phone=phone,telegram_username=username,comment=payload.comment.strip()); session.add(booking); await session.flush(); session.add(AdminNotification(booking_id=booking.id, message=f"Новая заявка: {booking.first_name} {booking.last_name}, {booking.phone}")); await session.execute(SeatHold.__table__.delete().where(SeatHold.movie_id == payload.movie_id,SeatHold.show_date == payload.show_date,SeatHold.session == payload.session,SeatHold.user_id == user.id)); await session.commit()
    return {"status":"pending","ticket_code":code,"total":booking.total,"message":"Спасибо за бронирование! В ближайшее время администратор свяжется с вами."}

@app.get("/api/admin/bookings")
async def admin_bookings(_: User = Depends(admin_required), session: AsyncSession = Depends(get_db)) -> list[dict[str, object]]:
    rows = await session.execute(select(Booking, Movie, User).join(Movie, Booking.movie_id == Movie.id).join(User, Booking.user_id == User.id).order_by(Booking.id.desc()))
    return [{"id":booking.id,"status":booking.status,"phone":booking.phone,"name":f"{booking.first_name} {booking.last_name}".strip(),"comment":booking.comment,"total":booking.total,"seats":booking.seats,"session":booking.session,"show_date":booking.show_date,"movie_id":movie.id,"movie":movie.title,"poster":movie.poster,"telegram_username":booking.telegram_username or user.username,"chat_url":f"https://t.me/{booking.telegram_username or user.username}" if booking.telegram_username or user.username else None,"proposed_session":booking.proposed_session,"admin_note":booking.admin_note} for booking, movie, user in rows]

@app.patch("/api/admin/bookings/{booking_id}/status")
async def update_booking_status(booking_id: int, payload: BookingStatusIn, _: User = Depends(admin_required), session: AsyncSession = Depends(get_db)) -> dict[str, str]:
    booking = await session.get(Booking, booking_id)
    if booking is None: raise HTTPException(404, "Booking not found")
    booking.status = payload.status
    session.add(UserNotification(user_id=booking.user_id,type="booking_status",title="Статус бронирования изменён",message=f"Заявка #{booking.id}: {payload.status}"))
    await session.commit(); return {"status":booking.status}

@app.patch("/api/admin/bookings/{booking_id}/decision")
async def decide_booking(booking_id: int, payload: BookingDecisionIn, _: User = Depends(admin_required), session: AsyncSession = Depends(get_db)) -> dict[str, object]:
    row = await session.execute(select(Booking, User, Movie).join(User, Booking.user_id == User.id).join(Movie, Booking.movie_id == Movie.id).where(Booking.id == booking_id))
    item = row.first()
    if item is None: raise HTTPException(404, "Booking not found")
    booking, user, movie = item
    if payload.action == "confirm":
        booking.status = "confirmed"
        booking.proposed_session = ""
        booking.admin_note = ""
        message = f"Ваша бронь #{booking.id} подтверждена: {movie.title}, {booking.show_date} {booking.session}."
    elif payload.action == "decline":
        booking.status = "cancelled"
        booking.admin_note = payload.reason.strip()
        message = f"Заявка #{booking.id} отклонена. Причина: {booking.admin_note or 'не указана'}."
    else:
        if not payload.proposed_session: raise HTTPException(422, "Proposed time is required")
        booking.proposed_session = payload.proposed_session
        booking.admin_note = payload.reason.strip()
        message = f"Nova Cinema предлагает другое время для заявки #{booking.id}: {booking.proposed_session}. {booking.admin_note}".strip()
    session.add(user_booking_notification(booking, "Nova Cinema", message))
    await session.commit()
    await send_telegram_message(user.telegram_id, message)
    return {"status":booking.status,"proposed_session":booking.proposed_session,"admin_note":booking.admin_note}

@app.patch("/api/profile/bookings/{booking_id}/proposal")
async def answer_booking_proposal(booking_id:int,payload:BookingProposalIn,user:User=Depends(current_user),session:AsyncSession=Depends(get_db))->dict[str,object]:
    booking=await session.scalar(select(Booking).where(Booking.id==booking_id,Booking.user_id==user.id))
    if booking is None: raise HTTPException(404,"Booking not found")
    if not booking.proposed_session: raise HTTPException(409,"No proposed time")
    if payload.action == "accept":
        booking.session = booking.proposed_session
        booking.proposed_session = ""
        booking.admin_note = ""
        message = f"Клиент согласился на новое время заявки #{booking.id}: {booking.session}"
    else:
        booking.status = "cancelled"
        booking.admin_note = "Клиент отказался от предложенного времени"
        message = f"Клиент отказался от нового времени заявки #{booking.id}"
    session.add(AdminNotification(booking_id=booking.id, message=message))
    await session.commit()
    return {"status":booking.status,"session":booking.session}

@app.get("/api/admin/settings/base-price")
async def base_price(_: User = Depends(admin_required), session: AsyncSession = Depends(get_db)) -> dict[str, int]:
    settings = await session.get(CinemaSettings, 1)
    return {"base_ticket_price": settings.base_ticket_price if settings else 30000}

@app.patch("/api/admin/settings/base-price")
async def update_base_price(payload: BasePriceIn, _: User = Depends(admin_required), session: AsyncSession = Depends(get_db)) -> dict[str, int]:
    settings = await session.get(CinemaSettings, 1)
    if settings is None: settings = CinemaSettings(id=1, base_ticket_price=payload.base_ticket_price); session.add(settings)
    else: settings.base_ticket_price = payload.base_ticket_price
    await session.commit(); return {"base_ticket_price":payload.base_ticket_price}

@app.get("/api/admin/notifications")
async def admin_notifications(_: User = Depends(admin_required), session: AsyncSession = Depends(get_db)) -> list[dict[str, object]]:
    rows = await session.scalars(select(AdminNotification).order_by(AdminNotification.id.desc()))
    return [{"id":item.id,"booking_id":item.booking_id,"message":item.message,"is_read":item.is_read,"created_at":item.created_at} for item in rows]

@app.patch("/api/admin/notifications/{notification_id}/read")
async def read_notification(notification_id: int, _: User = Depends(admin_required), session: AsyncSession = Depends(get_db)) -> dict[str, bool]:
    item = await session.get(AdminNotification, notification_id)
    if item is None: raise HTTPException(404, "Notification not found")
    item.is_read = True; await session.commit(); return {"is_read": True}

@app.get("/api/admin/dashboard")
async def dashboard(_: User = Depends(admin_required), session: AsyncSession = Depends(get_db)) -> dict[str, object]:
    movie_count = await session.scalar(select(func.count()).select_from(Movie)) or 0
    booking_count = await session.scalar(select(func.count()).select_from(Booking)) or 0
    base_session_rows = await session.scalars(select(Movie.sessions_json))
    active_session_count = await session.scalar(select(func.count()).select_from(SessionPrice).where(SessionPrice.status == "active")) or 0
    income = await session.scalar(select(func.coalesce(func.sum(Booking.total), 0)).where(Booking.status != "cancelled")) or 0
    status_rows = await session.execute(select(Booking.status, func.count()).group_by(Booking.status))
    counts = {value: 0 for value in ("pending","confirmed","cancelled","completed")}
    counts.update({status_name: count for status_name, count in status_rows})
    notices = list(await session.scalars(select(AdminNotification).order_by(AdminNotification.id.desc()).limit(5)))
    recent = list(await session.scalars(select(Booking).order_by(Booking.id.desc()).limit(5)))
    base_session_count = sum(len(json.loads(value)) for value in base_session_rows)
    return {"movies":movie_count,"active_sessions":base_session_count+active_session_count,"bookings":booking_count,"potential_income":income,"statuses":counts,"recent_bookings":[{"id":item.id,"name":f"{item.first_name} {item.last_name}".strip(),"phone":item.phone,"status":item.status,"total":item.total} for item in recent],"notifications":[{"id":item.id,"booking_id":item.booking_id,"message":item.message,"is_read":item.is_read,"created_at":item.created_at} for item in notices]}

@app.post("/api/admin/uploads")
async def upload_image(file: UploadFile = File(...), _: User = Depends(admin_required)) -> dict[str, str]:
    if not file.content_type or not file.content_type.startswith("image/"): raise HTTPException(422, "Only image uploads are allowed")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}: raise HTTPException(422, "Unsupported image format")
    content = await file.read()
    if len(content) > 5_000_000: raise HTTPException(413, "Image is too large")
    signatures = {".jpg": (b"\xff\xd8\xff",), ".jpeg": (b"\xff\xd8\xff",), ".png": (b"\x89PNG\r\n\x1a\n",), ".webp": (b"RIFF",)}
    if not any(content.startswith(signature) for signature in signatures[suffix]): raise HTTPException(422, "Invalid image content")
    if suffix == ".webp" and content[8:12] != b"WEBP": raise HTTPException(422, "Invalid image content")
    filename = f"{uuid.uuid4().hex}{suffix}"
    await asyncio.to_thread((UPLOAD_DIR / filename).write_bytes, content)
    return {"url": f"/uploads/{filename}"}

@app.get("/api/admin/movies")
async def admin_movies(lang: str = "ru", _: User = Depends(admin_required), session: AsyncSession = Depends(get_db)) -> list[dict[str, object]]:
    result = await session.scalars(select(Movie).options(selectinload(Movie.reviews)).order_by(Movie.sort_order, Movie.id))
    return [serialize_movie(movie, language=lang) for movie in result]

@app.post("/api/admin/movies/lookup")
async def lookup_movie(payload: MovieLookupIn, _: User = Depends(admin_required)) -> dict[str, object]:
    return await lookup_movie_payload(payload.title)

@app.post("/api/admin/movies")
async def create_movie(payload: MovieIn, _: User = Depends(admin_required), session: AsyncSession = Depends(get_db)) -> dict[str, object]:
    values, warning = await localize_movie_payload(payload)
    item = Movie(**values, sessions_json="[]"); session.add(item); await session.commit(); return {"id":item.id,"translation_warning":warning}

@app.patch("/api/admin/movies/{movie_id}")
async def edit_movie(movie_id: int, payload: MovieIn, _: User = Depends(admin_required), session: AsyncSession = Depends(get_db)) -> dict[str, object]:
    item = await session.get(Movie,movie_id)
    if item is None: raise HTTPException(404,"Movie not found")
    values, warning = await localize_movie_payload(payload)
    for key,value in values.items(): setattr(item,key,value)
    await session.commit(); return {"status":"updated","translation_warning":warning}

@app.delete("/api/admin/movies/{movie_id}")
async def delete_movie(movie_id: int, _: User = Depends(admin_required), session: AsyncSession = Depends(get_db)) -> dict[str,str]:
    item=await session.get(Movie,movie_id)
    if item is None: raise HTTPException(404,"Movie not found")
    if await session.scalar(select(Booking.id).where(Booking.movie_id == movie_id).limit(1)) is not None: raise HTTPException(409,"Movie has bookings")
    await session.delete(item); await session.commit(); return {"status":"deleted"}

@app.get("/api/admin/sessions")
async def admin_sessions(_: User = Depends(admin_required), session: AsyncSession = Depends(get_db)) -> list[dict[str,object]]:
    settings = await session.get(CinemaSettings, 1)
    base_price_value = settings.base_ticket_price if settings and settings.base_ticket_price > 0 else 30000
    rows=await session.execute(select(SessionPrice, Movie).join(Movie, SessionPrice.movie_id == Movie.id).order_by(SessionPrice.show_date.desc(), SessionPrice.session))
    return [{"id":item.id,"movie_id":item.movie_id,"movie":movie.title,"show_date":item.show_date,"session":item.session,"ticket_price":item.ticket_price,"resolved_price":item.ticket_price or movie.ticket_price or base_price_value,"seats_count":item.seats_count,"status":item.status} for item, movie in rows]

@app.post("/api/admin/sessions")
async def create_session(payload: SessionIn, _: User = Depends(admin_required), session: AsyncSession = Depends(get_db)) -> dict[str,int]:
    if await session.get(Movie, payload.movie_id) is None: raise HTTPException(404,"Movie not found")
    if await session.scalar(select(SessionPrice.id).where(SessionPrice.movie_id == payload.movie_id, SessionPrice.show_date == payload.show_date, SessionPrice.session == payload.session)) is not None: raise HTTPException(409,"Session already exists")
    item=SessionPrice(**payload.model_dump()); session.add(item); await session.commit(); return {"id":item.id}

@app.patch("/api/admin/sessions/{session_id}")
async def edit_session(session_id: int,payload: SessionIn,_:User=Depends(admin_required),session:AsyncSession=Depends(get_db))->dict[str,str]:
    item=await session.get(SessionPrice,session_id)
    if item is None: raise HTTPException(404,"Session not found")
    if await session.get(Movie, payload.movie_id) is None: raise HTTPException(404,"Movie not found")
    duplicate = await session.scalar(select(SessionPrice.id).where(SessionPrice.movie_id == payload.movie_id, SessionPrice.show_date == payload.show_date, SessionPrice.session == payload.session, SessionPrice.id != session_id))
    if duplicate is not None: raise HTTPException(409,"Session already exists")
    for key,value in payload.model_dump().items(): setattr(item,key,value)
    await session.commit(); return {"status":"updated"}

@app.delete("/api/admin/sessions/{session_id}")
async def delete_session(session_id:int,_:User=Depends(admin_required),session:AsyncSession=Depends(get_db))->dict[str,str]:
    item=await session.get(SessionPrice,session_id)
    if item is None: raise HTTPException(404,"Session not found")
    await session.delete(item); await session.commit(); return {"status":"deleted"}
