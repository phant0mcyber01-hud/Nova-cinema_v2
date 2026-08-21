from __future__ import annotations

import asyncio
import html
import logging
import os
from pathlib import Path
from urllib.parse import urlparse

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonWebApp, WebAppInfo
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.orm import selectinload

ENV_PATH = Path(__file__).resolve().with_name(".env")
load_dotenv(dotenv_path=ENV_PATH, override=True)

from backend.core.db import SessionLocal
from backend.models import Movie
from backend.services.catalog import serialize_movie

_bot_token = os.getenv("BOT_TOKEN")
if _bot_token is None:
    raise RuntimeError("BOT_TOKEN is not set")
BOT_TOKEN: str = _bot_token.strip('"')
WEBAPP_URL = os.getenv("WEBAPP_URL", "")
WEBAPP_BUTTON_TEXT = "🚀 Открыть Nova Cinema"
WEBAPP_MENU_TEXT = "Nova Cinema"
ADMIN_TELEGRAM_IDS = {
    int(value.strip())
    for value in os.getenv("ADMIN_TELEGRAM_IDS", "").split(",")
    if value.strip().isdigit()
}

dp = Dispatcher()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nova-cinema-bot")


def validate_webapp_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise RuntimeError("WEBAPP_URL must be an absolute HTTPS URL")
    if "your-domain.example" in url:
        raise RuntimeError("WEBAPP_URL still points to placeholder your-domain.example")
    return url.rstrip("/")


WEBAPP_URL = validate_webapp_url(WEBAPP_URL)


def normalize_webapp_url(url: str | None) -> str:
    return (url or "").rstrip("/")


def mini_app_url(path: str = "") -> str:
    if not path:
        return WEBAPP_URL
    return f"{WEBAPP_URL}/{path.lstrip('/')}"


def public_asset_url(value: str) -> str:
    if value.startswith(("http://", "https://")):
        return value
    return mini_app_url(value)


def create_webapp_info(path: str = "") -> WebAppInfo:
    url = mini_app_url(path)
    logger.info("Creating WebAppInfo with URL=%s", url)
    return WebAppInfo(url=url)


async def configure_menu_button(bot: Bot) -> None:
    logger.info("Registering Telegram MenuButtonWebApp with URL=%s", WEBAPP_URL)
    await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text=WEBAPP_MENU_TEXT, web_app=create_webapp_info()))
    current_button = await bot.get_chat_menu_button()
    current_url = getattr(getattr(current_button, "web_app", None), "url", None)
    logger.info("Telegram Bot API menu button URL=%s", current_url)
    if normalize_webapp_url(current_url) != normalize_webapp_url(WEBAPP_URL):
        raise RuntimeError(f"Telegram menu button URL mismatch: {current_url!r}")


async def fetch_published_movies() -> list[dict[str, object]]:
    async with SessionLocal() as session:
        result = await session.scalars(
            select(Movie)
            .options(selectinload(Movie.reviews))
            .where(Movie.is_published.is_(True))
            .order_by(Movie.sort_order, Movie.id)
        )
        return [serialize_movie(movie) for movie in result]


async def fetch_published_movie(movie_id: int) -> dict[str, object] | None:
    async with SessionLocal() as session:
        movie = await session.scalar(
            select(Movie)
            .options(selectinload(Movie.reviews))
            .where(Movie.id == movie_id, Movie.is_published.is_(True))
        )
        return serialize_movie(movie) if movie else None


def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=WEBAPP_BUTTON_TEXT, web_app=create_webapp_info())],
            [InlineKeyboardButton(text="🎬 Каталог фильмов", callback_data="movies")],
            [InlineKeyboardButton(text="🎫 Мои бронирования", web_app=create_webapp_info("/profile/bookings"))],
            [InlineKeyboardButton(text="ℹ️ О кинотеатре", callback_data="about")],
        ]
    )


def movie_keyboard(movie: dict[str, object]) -> InlineKeyboardMarkup:
    movie_id = int(movie["id"])
    trailer_id = str(movie.get("trailer_id") or "")
    rows: list[list[InlineKeyboardButton]] = []
    if trailer_id:
        rows.append([InlineKeyboardButton(text="▶ Смотреть трейлер", url=f"https://youtu.be/{trailer_id}")])
    rows.append([InlineKeyboardButton(text="🎟 Забронировать", web_app=create_webapp_info(f"/booking/{movie_id}/date"))])
    rows.append([InlineKeyboardButton(text="◀ Назад", callback_data="movies")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def shorten(value: object, limit: int = 620) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}…"


def movie_caption(movie: dict[str, object]) -> str:
    return (
        f"🎬 <b>{html.escape(str(movie['title']))}</b>\n\n"
        f"🏷 <b>Жанр:</b> {html.escape(str(movie['genre']))}\n"
        f"🔞 <b>Возраст:</b> {movie['age']}+\n"
        f"⏱ <b>Длительность:</b> {movie['duration']} мин\n"
        f"⭐ <b>IMDb:</b> {movie['imdb']} · <b>КиноПоиск:</b> {movie['kinopoisk']}\n\n"
        f"{html.escape(shorten(movie.get('description')))}"
    )


async def show_text(message: types.Message, text: str, keyboard: InlineKeyboardMarkup) -> None:
    await message.answer(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)


async def replace_callback_message(call: CallbackQuery, text: str, keyboard: InlineKeyboardMarkup) -> None:
    if call.message is None:
        return
    try:
        await call.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    except TelegramBadRequest:
        try:
            await call.message.delete()
        except TelegramBadRequest:
            pass
        await call.message.answer(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)


@dp.message(CommandStart())
async def cmd_start(message: types.Message) -> None:
    text = (
        "<b>🎬 Добро пожаловать в Nova Cinema!</b>\n\n"
        "Откройте Mini App или выберите фильм прямо в каталоге бота. "
        "Каталог берётся из той же PostgreSQL-базы, что и приложение."
    )
    await show_text(message, text, main_keyboard())


@dp.callback_query(F.data == "main")
async def cb_main(call: CallbackQuery) -> None:
    await replace_callback_message(call, "<b>🎬 Главное меню Nova Cinema</b>", main_keyboard())
    await call.answer()


@dp.callback_query(F.data == "movies")
async def cb_movies(call: CallbackQuery) -> None:
    movies = await fetch_published_movies()
    if not movies:
        await replace_callback_message(
            call,
            "<b>🎬 Каталог фильмов</b>\n\nПока нет опубликованных фильмов.",
            InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀ Главное меню", callback_data="main")]]),
        )
        await call.answer()
        return
    rows = [
        [InlineKeyboardButton(text=f"🎬 {movie['title']} · {movie['age']}+", callback_data=f"movie_{movie['id']}")]
        for movie in movies
    ]
    rows.append([InlineKeyboardButton(text="◀ Главное меню", callback_data="main")])
    await replace_callback_message(
        call,
        f"<b>🎬 Каталог фильмов</b>\n\nВыберите фильм из библиотеки Nova Cinema. Сейчас доступно: <b>{len(movies)}</b>.",
        InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await call.answer()


@dp.callback_query(F.data.startswith("movie_"))
async def cb_movie_detail(call: CallbackQuery) -> None:
    movie_id = int(str(call.data).split("_", 1)[1])
    movie = await fetch_published_movie(movie_id)
    if movie is None:
        await call.answer("Фильм не найден или скрыт", show_alert=True)
        return
    if call.message is None:
        return
    try:
        await call.message.delete()
    except TelegramBadRequest:
        pass
    poster = public_asset_url(str(movie.get("poster") or ""))
    try:
        await call.message.answer_photo(
            photo=poster,
            caption=movie_caption(movie),
            reply_markup=movie_keyboard(movie),
            parse_mode=ParseMode.HTML,
        )
    except TelegramBadRequest:
        await call.message.answer(movie_caption(movie), reply_markup=movie_keyboard(movie), parse_mode=ParseMode.HTML)
    await call.answer()


@dp.callback_query(F.data == "about")
async def cb_about(call: CallbackQuery) -> None:
    text = (
        "<b>ℹ️ О кинотеатре Nova Cinema</b>\n\n"
        "📍 <b>Адрес:</b> Юксалиш 97\n"
        "☎️ <b>Телефон:</b> +998 91 326 20 65\n"
        "💬 <b>Telegram:</b> https://t.me/novasinema\n"
        "📸 <b>Instagram:</b> https://www.instagram.com/nova_cinema__\n\n"
        "Кино, которое остаётся с вами."
    )
    await replace_callback_message(
        call,
        text,
        InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀ Главное меню", callback_data="main")]]),
    )
    await call.answer()


@dp.message(Command("admin"))
async def cmd_admin(message: types.Message) -> None:
    if message.from_user is None or message.from_user.id not in ADMIN_TELEGRAM_IDS:
        return
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📲 Открыть админку", web_app=create_webapp_info("/admin"))],
            [InlineKeyboardButton(text="🎬 Каталог фильмов", callback_data="movies")],
        ]
    )
    await message.answer("<b>Админ-раздел Nova Cinema</b>\n\nУправление контентом доступно внутри Mini App.", reply_markup=keyboard)


async def main() -> None:
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    logger.info("Loaded .env from %s", ENV_PATH)
    logger.info("Runtime WEBAPP_URL=%s", WEBAPP_URL)
    await configure_menu_button(bot)
    logger.info("Nova Cinema bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
