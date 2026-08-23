"""Fill the database with a believable cinema, for showing the app to someone.

Everything here is data an administrator would enter through the panel — the
About text, the bot handle, a few promotions, and a history of requests in
every status, so the admin screens and the personal cabinet are not empty.

    python demo_data.py

Safe to run twice: it skips what already exists. It never touches the movie
catalog — that is seed_movies.py.
"""
from __future__ import annotations

import asyncio
from datetime import timedelta

from sqlalchemy import select

from backend.core.db import SessionLocal, utcnow
from backend.models import Booking, Bonus, Movie, Review, Show, User
from backend.services.booking import cinema_now
from backend.services.settings import get_settings

BOT_USERNAME = "NOVA_CINEMA_searchbot"

ABOUT_RU = (
    "Один зал на пятнадцать мест, лазерный проектор и звук, ради которого стоит прийти. "
    "Мы показываем и премьеры, и то, что хочется пересматривать. Билеты бронируются "
    "в Telegram: вы оставляете заявку, мы перезваниваем и подтверждаем место."
)
ABOUT_UZ = (
    "Oʻn besh oʻrinli bitta zal, lazerli proyektor va kelishga arziydigan ovoz. "
    "Biz premyeralarni ham, qayta koʻrgingiz keladigan filmlarni ham namoyish etamiz. "
    "Chiptalar Telegram orqali band qilinadi: siz ariza qoldirasiz, biz qoʻngʻiroq qilib tasdiqlaymiz."
)

BONUSES = [
    (
        "Второй билет со скидкой", "Ikkinchi chipta chegirmali",
        "Скидка 20% на второй билет по будням до 17:00. Промокод NOVA10 при подтверждении заявки.",
        "Ish kunlari 17:00 gacha ikkinchi chiptaga 20% chegirma. Arizani tasdiqlashda NOVA10 promokodi.",
        1,
    ),
    (
        "Первый визит", "Birinchi tashrif",
        "Бронируете у нас впервые — попкорн в подарок. Скажите администратору промокод WELCOME.",
        "Bizda birinchi marta band qilyapsizmi — popkorn sovgʻa. Administratorga WELCOME promokodini ayting.",
        2,
    ),
    (
        "День рождения", "Tugʻilgan kun",
        "В день рождения и три дня после — скидка 15% на весь зал. Промокод NOVASINEMA.",
        "Tugʻilgan kuningizda va undan keyingi uch kun ichida butun zalga 15% chegirma. NOVASINEMA promokodi.",
        3,
    ),
]

#: telegram_id, first name, last name, phone, @username
VIEWERS = [
    (111111111, "Алина", "Каримова", "+998901234567", "demo_viewer"),
    (222222222, "Тимур", "Расулов", "+998907654321", "timur_r"),
    (333333333, "Мадина", "Юсупова", "+998935550101", "madina_y"),
    (444444444, "Санжар", "Ким", "+998971112233", "sanjar_k"),
]

#: viewer index, status, seats, days ahead, comment
REQUESTS = [
    (0, "confirmed", "2-2,2-3", 1, "Годовщина, посадите вместе"),
    (0, "pending", "1-4", 2, ""),
    (1, "contacting", "3-1,3-2", 1, "Перезвоните после 18:00"),
    (2, "confirmed", "1-1,1-2,1-3", 2, ""),
    (3, "pending", "2-5", 3, "Можно ли оплатить на месте?"),
    (1, "cancelled", "3-5", 1, "Не смогу прийти"),
]

#: viewer index, seats, days ago, rating, review text
HISTORY = [
    (0, "2-1,2-2", 3, 5, "Идеальный звук и очень уютно. Вернёмся ещё раз."),
    (1, "1-3", 5, 5, "Маленький зал, но именно этим и хорош — как домашний кинотеатр."),
    (2, "3-3,3-4", 7, 4, "Понравилось всё, кроме очереди на входе. Фильм отличный."),
]


async def ensure_user(session, telegram_id, first_name, last_name, phone, username) -> User:
    user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
    if user is None:
        user = User(
            telegram_id=telegram_id,
            name=(first_name + " " + last_name).strip(),
            username=username,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
        )
        session.add(user)
        await session.flush()
    return user


async def ensure_show(session, movie_id: int, show_date: str, start_time: str) -> None:
    exists = await session.scalar(
        select(Show.id).where(
            Show.movie_id == movie_id, Show.show_date == show_date, Show.start_time == start_time
        )
    )
    if exists is None:
        session.add(Show(movie_id=movie_id, show_date=show_date, start_time=start_time))


def seat_count(seats: str) -> int:
    return len([seat for seat in seats.split(",") if seat])


async def main() -> None:
    async with SessionLocal() as session:
        settings = await get_settings(session)
        settings.bot_username = settings.bot_username or BOT_USERNAME
        settings.about = settings.about or ABOUT_RU
        settings.about_uz = settings.about_uz or ABOUT_UZ

        if (await session.scalars(select(Bonus))).first() is None:
            for title, title_uz, body, body_uz, order in BONUSES:
                session.add(Bonus(
                    title=title, title_uz=title_uz, text=body, text_uz=body_uz,
                    is_active=True, sort_order=order,
                ))

        movies = list(await session.scalars(
            select(Movie).order_by(Movie.sort_order, Movie.id).limit(6)
        ))
        if not movies:
            raise SystemExit("Каталог пуст — сначала запустите seed_movies.py")

        if (await session.scalars(select(Booking))).first() is not None:
            await session.commit()
            print("Заявки уже есть: обновлены только настройки и бонусы.")
            return

        users = [await ensure_user(session, *viewer) for viewer in VIEWERS]
        today = cinema_now(settings.timezone_offset_minutes).date()
        price = settings.base_ticket_price

        for index, (viewer, status, seats, offset, comment) in enumerate(REQUESTS):
            movie = movies[index % len(movies)]
            show_date = (today + timedelta(days=offset)).isoformat()
            times = list(await session.scalars(
                select(Show.start_time)
                .where(Show.movie_id == movie.id, Show.show_date == show_date)
                .order_by(Show.start_time)
            ))
            if not times:
                continue
            user = users[viewer]
            session.add(Booking(
                user_id=user.id, movie_id=movie.id, show_date=show_date, session=times[-1],
                seats=seats, code=str(user.telegram_id), ticket_price=price,
                total=price * seat_count(seats), status=status,
                first_name=user.first_name, last_name=user.last_name,
                phone=user.phone, telegram_username=user.username, comment=comment,
                created_at=utcnow() - timedelta(hours=index * 5 + 1),
            ))

        for index, (viewer, seats, days_ago, rating, body) in enumerate(HISTORY):
            movie = movies[index % len(movies)]
            show_date = (today - timedelta(days=days_ago)).isoformat()
            await ensure_show(session, movie.id, show_date, "19:00")
            user = users[viewer]
            session.add(Booking(
                user_id=user.id, movie_id=movie.id, show_date=show_date, session="19:00",
                seats=seats, code=str(user.telegram_id), ticket_price=price,
                total=price * seat_count(seats), status="watched",
                first_name=user.first_name, last_name=user.last_name,
                phone=user.phone, telegram_username=user.username, comment="",
                created_at=utcnow() - timedelta(days=days_ago + 1),
                completed_at=utcnow() - timedelta(days=days_ago),
            ))
            session.add(Review(
                movie_id=movie.id, user_id=user.id, rating=rating, text=body, approved=True,
            ))

        await session.commit()
        print(
            "Готово: " + str(len(REQUESTS)) + " заявок, " + str(len(HISTORY))
            + " просмотров с отзывами, " + str(len(BONUSES))
            + " бонуса, username бота и текст «О нас»."
        )


if __name__ == "__main__":
    asyncio.run(main())
