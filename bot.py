from __future__ import annotations

import asyncio
import html
import logging
from urllib.parse import urlparse

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonWebApp, WebAppInfo
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.core import config
from backend.core.db import SessionLocal
from backend.models import Movie
from backend.services.catalog import serialize_movie
from backend.services.deep_link import movie_id_from_payload
from backend.services.settings import get_settings

# The environment is read and normalised in one place for the whole project;
# the bot parsing it a second time is how the two drift apart.
BOT_TOKEN: str = config.bot_token()
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is empty: put the BotFather token in .env")
WEBAPP_URL = config.WEBAPP_URL
WEBAPP_BUTTON_TEXT = "🚀 Открыть Nova Cinema"
WEBAPP_MENU_TEXT = "Nova Cinema"
ADMIN_TELEGRAM_IDS = config.ADMIN_TELEGRAM_IDS

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


async def fetch_settings() -> dict[str, object]:
    async with SessionLocal() as session:
        settings = await get_settings(session)
        return {
            "name": settings.name,
            "address": settings.address,
            "phone": settings.phone,
            "telegram_url": settings.telegram_url,
            "instagram_url": settings.instagram_url,
            "work_hours": settings.work_hours,
            "about": settings.about,
        }


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


async def send_movie_card(message: types.Message, movie: dict[str, object]) -> None:
    """Poster with caption, falling back to plain text if Telegram rejects the image."""
    poster = public_asset_url(str(movie.get("poster") or ""))
    try:
        await message.answer_photo(
            photo=poster,
            caption=movie_caption(movie),
            reply_markup=movie_keyboard(movie),
            parse_mode=ParseMode.HTML,
        )
    except TelegramBadRequest:
        await message.answer(movie_caption(movie), reply_markup=movie_keyboard(movie), parse_mode=ParseMode.HTML)


# Registered before the plain /start so a shared link is not swallowed by it.
@dp.message(CommandStart(deep_link=True))
async def cmd_start_shared_movie(message: types.Message, command: CommandObject) -> None:
    """Handles t.me/<bot>?start=movie_<id> — the `startapp` form opens the Mini App directly."""
    movie_id = movie_id_from_payload(command.args)
    if movie_id is None:
        await show_text(
            message,
            "<b>Ссылка не распознана</b>\n\nОткройте каталог и выберите фильм.",
            main_keyboard(),
        )
        return
    movie = await fetch_published_movie(movie_id)
    if movie is None:
        await show_text(
            message,
            "<b>Фильм недоступен</b>\n\nВозможно, он снят с показа или ссылка устарела.",
            main_keyboard(),
        )
        return
    await send_movie_card(message, movie)


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
    await send_movie_card(call.message, movie)
    await call.answer()


@dp.callback_query(F.data == "about")
async def cb_about(call: CallbackQuery) -> None:
    settings = await fetch_settings()
    lines = [f"<b>ℹ️ О кинотеатре {html.escape(str(settings['name']))}</b>", ""]
    if settings["address"]:
        lines.append(f"📍 <b>Адрес:</b> {html.escape(str(settings['address']))}")
    if settings["phone"]:
        lines.append(f"☎️ <b>Телефон:</b> {html.escape(str(settings['phone']))}")
    if settings["work_hours"]:
        lines.append(f"🕒 <b>Время работы:</b> {html.escape(str(settings['work_hours']))}")
    if settings["telegram_url"]:
        lines.append(f"💬 <b>Telegram:</b> {html.escape(str(settings['telegram_url']))}")
    if settings["instagram_url"]:
        lines.append(f"📸 <b>Instagram:</b> {html.escape(str(settings['instagram_url']))}")
    if settings["about"]:
        lines.extend(["", html.escape(str(settings["about"]))])
    await replace_callback_message(
        call,
        "\n".join(lines),
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
    logger.info("Loaded .env from %s", config.PROJECT_ROOT / ".env")
    logger.info("Runtime WEBAPP_URL=%s", WEBAPP_URL)
    await configure_menu_button(bot)
    logger.info("Nova Cinema bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
