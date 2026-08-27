"""One-off insert of the client's real movie list into the catalog.

Unlike seed_movies.py (demo data, never touched), this script adds the
titles the client actually sent for their cinema. It is idempotent: run it
as many times as you want, existing titles (by exact `title` match) are
skipped, nothing is overwritten or duplicated.

Usage (from the project root, with the venv active and a working DB):

    python add_client_movies.py

Posters: a handful of titles below ship with a real poster file under
assets/client_movies/ (copied from what the client sent in chat). On first
run the script copies those files into UPLOAD_DIR and serves them at
/uploads/<file>. Titles without a shipped poster get a neutral placeholder
path (poster="") — fill the real poster in later through the admin panel,
this does not block anything else in the app.

Does NOT touch seed_movies.py or any existing row.
"""
from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import select

load_dotenv(Path(__file__).resolve().with_name(".env"), override=False)

from backend.core.config import UPLOAD_DIR
from backend.core.db import SessionLocal
from backend.models import Movie

ASSETS_DIR = Path(__file__).resolve().with_name("assets") / "client_movies"


def movie(
    *,
    title: str,
    genre: str,
    description: str,
    duration: int,
    age: int,
    year: int,
    country: str = "",
    director: str = "",
    cast: list[str] | None = None,
    poster_file: str | None = None,
    sort_order: int,
) -> dict[str, Any]:
    return {
        "title": title,
        "genre": genre,
        "description": description,
        "poster": f"/uploads/{poster_file}" if poster_file else "",
        "gallery_json": "[]",
        "trailer_id": "",
        "duration": duration,
        "age": age,
        "year": year,
        "country": country,
        "director": director,
        "cast_json": json.dumps(cast or [], ensure_ascii=False),
        "imdb": 0,
        "kinopoisk": 0,
        "internal_rating": None,
        "ticket_price": None,
        "is_published": True,
        "sort_order": sort_order,
        "_poster_file": poster_file,
    }


# Titles already in the catalog (from the client's own posts, watermarked
# "NOVA CINEMA" or matching the original 8-film seed) are intentionally
# excluded here: Проклятие Ла Йороны, Майкл, Обсессия, История игрушек 5,
# Зловещие мертвецы: Пекло, Одиссея, Миньоны и Монстры, Человек-паук: Новый
# день, Очень страшное кино 6, Закулисье реальности, Выход 8.

CLIENT_MOVIES: list[dict[str, Any]] = [
    movie(
        title="От заката до рассвета",
        genre="Комедия",
        description="Беременная девушка ночью захотела банан, она просит мужа купить ей его. Он уезжает и сначала попадает в полицию, потом в квартиру незнакомой женщины, которая оказывается авантюристкой. А в это время дома у его жены начинаются схватки.",
        duration=92, age=16, year=2009, country="Узбекистан", sort_order=100,
    ),
    movie(
        title="Аватар 3: Огонь и пепел",
        genre="Фантастика",
        description="Джейк Салли, Нейтири и их дети переживают смерть Нетейама. Противостояние с корпорацией RDA обостряется, и теперь семье предстоит столкнуться с враждебным племенем На'ви во главе с Варанг.",
        duration=195, age=16, year=2025, country="США", director="Джеймс Кэмерон",
        poster_file="img_122944a3ee98.jpg", sort_order=101,
    ),
    movie(
        title="Астрал 5: Всё началось",
        genre="Ужасы",
        description="Семья Ламберт стремится раскрыть тайну, из-за которой они оказались в опасной связи с миром духов. Они переезжают в дом матери Джоша, но, как оказывается, туда вселяются не только они.",
        duration=107, age=16, year=2023, country="США", director="Патрик Уилсон",
        poster_file="img_7fb7e55de10f.jpg", sort_order=102,
    ),
    movie(
        title="Астрал: Личины",
        genre="Ужасы",
        description="Медиум Элиза Рейнер неохотно соглашается использовать свои способности для установления связи с мертвыми, чтобы помочь девочке-подростку, которая стала мишенью опасной сверхъестественной сущности.",
        duration=104, age=16, year=2010, country="США", director="Ли Уоннелл",
        poster_file="img_11326d977d93.jpg", sort_order=103,
    ),
    movie(
        title="Астрал: Красная дверь",
        genre="Ужасы",
        description="Детство Элизы было трудным. Много лет спустя она всё ещё пытается восстановить в памяти события той ужасной ночи, когда получает просьбу о помощи от мужчины, которого одолели призраки.",
        duration=107, age=16, year=2023, country="США", director="Патрик Уилсон",
        poster_file="img_05443bc5079a.jpg", sort_order=104,
    ),
    movie(
        title="Астрал 2",
        genre="Ужасы",
        description="Первокурсника Далтона терзают кошмары из прошлого. Парень начинает рисовать загадочную дверь, связанную с его детскими годами. А Джош, который тоже забыл важную часть своей жизни, во время обследования вдруг видит страшного призрака.",
        duration=105, age=16, year=2013, country="США", director="Джеймс Ван",
        poster_file="img_f4ecb668308c.jpg", sort_order=105,
    ),
    movie(
        title="Твоё имя",
        genre="Аниме, Мелодрама",
        description="Токийский парень Таки и провинциальная девушка Мицуха обнаруживают, что между ними существует странная связь. Во сне они меняются телами и проживают жизни друг друга.",
        duration=106, age=12, year=2016, country="Япония", director="Макото Синкай",
        poster_file="img_6d2a68f9fa80.jpg", sort_order=106,
    ),
    movie(
        title="В метре друг от друга",
        genre="Мелодрама",
        description="Влюбленные должны находиться не ближе метра друг от друга, им недоступно даже прикосновение. Но истинная любовь не знает границ.",
        duration=116, age=16, year=2019, country="США", director="Джастин Бэлдони",
        sort_order=107,
    ),
    movie(
        title="Возвращение в Сайлент Хилл",
        genre="Ужасы",
        description="После исчезновения возлюбленной художник Джеймс Сандерленд отправляется в курортный городок Сайлент Хилл. Но Сайлент Хилл уже не тот.",
        duration=110, age=18, year=2026, country="Франция", director="Кристоф Ганс",
        sort_order=108,
    ),
    movie(
        title="Мама",
        genre="Ужасы",
        description="Пара берет в дом девочек-сирот, а вместе с ними — зловещее нечто. Найденные в заброшенной хижине сироты не одиноки, у них есть мама, и она приходит из тьмы…",
        duration=100, age=16, year=2013, country="Испания, Канада", director="Андрес Мускетти",
        sort_order=109,
    ),
    movie(
        title="Проклятие Аннабель",
        genre="Ужасы",
        description="Демон, порожденный сатанистами, вселяется в куклу и начинает мстить. Джон находит идеальный подарок для своей жены — редкую старинную куклу. Но восторг от подарка продлился недолго.",
        duration=99, age=16, year=2014, country="США",
        sort_order=110,
    ),
    movie(
        title="Одержимые",
        genre="Ужасы",
        description="Грэм узнаёт, что младшего брата сразил недуг, погубивший их отца. Мужчине приходится вернуться в отчий дом, когда он узнаёт, что младший брат страдает от той же странной болезни на грани одержимости.",
        duration=104, age=18, year=2025, country="",
        sort_order=111,
    ),
    movie(
        title="Друг в океане",
        genre="Драма, Семейный",
        description="Эбби увлекается дайвингом. Во время очередного погружения девушка видит большого синего групера — рыбу на грани исчезновения. Групера охраняет опасная банда браконьеров.",
        duration=102, age=6, year=2023, country="Австралия", director="Роберт Коннолли",
        cast=["Миа Васиковска", "Рада Митчелл", "Эрик Бана"],
        poster_file="img_963b3a47c8ed.jpg", sort_order=112,
    ),
    movie(
        title="Танцуй сердцем",
        genre="Мелодрама, Танцевальный",
        description="Хип-хопер Джозеф и балерина Хлоя создают танец на стыке двух стилей. Психологизм, зрелищная хореография и парижский шарм.",
        duration=104, age=12, year=2019, country="Франция", director="Ладислас Шолла",
        cast=["Райан Бенсетти", "Алексиа Джордано"],
        poster_file="img_10688ef2a7ba.jpg", sort_order=113,
    ),
    movie(
        title="Семья в аренду",
        genre="Драма, Комедия",
        description="Не особо удачливый американский актёр Филлип уже 7 лет живёт в Японии. Однажды ему предлагают работу в фирме «Семья в аренду», где ему нужно играть необычные роли для обычных людей.",
        duration=105, age=12, year=2025, country="США, Япония", director="Хикари",
        cast=["Брендан Фрейзер"],
        poster_file="img_e343564e8ba8.jpg", sort_order=114,
    ),
    movie(
        title="Звук свободы",
        genre="Драма, Триллер",
        description="Спецагент пытается раскрыть сеть по торговле детьми. Оперативник Тим Баллард втирается в доверие к распространителю детского порно, чтобы освободить проданных в сексуальное рабство детей.",
        duration=131, age=18, year=2023, country="США", director="Алехандро Монтеверде",
        poster_file="img_c8caebb2be8f.jpg", sort_order=115,
    ),
    movie(
        title="Сводишь с ума",
        genre="Мелодрама, Комедия",
        description="Алиса и Ваня живут в одной квартире — но в разных мирах. В квартире начинает сбоить зеркало, показывающее параллельную реальность.",
        duration=98, age=16, year=2025, country="Россия", director="Даша Лебедева",
        cast=["Мила Ершова", "Юрий Насонов"],
        poster_file="img_a38f0bf16829.jpg", sort_order=116,
    ),
    movie(
        title="Зеркала",
        genre="Ужасы, Триллер",
        description="Спившийся полицейский раскрывает тайну зеркал-убийц. Устроившись ночным сторожем в сгоревший универмаг, он начинает замечать что-то зловещее в декоративных зеркалах.",
        duration=110, age=18, year=2008, country="США", director="Александр Ажа",
        sort_order=117,
    ),
    movie(
        title="Звонок",
        genre="Ужасы",
        description="Рэйчел разгадывает тайну адской кассеты. Журналистка расследует загадочные смерти молодых людей и обнаруживает, что кассета-убийца попала в руки к её маленькому сыну.",
        duration=115, age=16, year=2002, country="США", director="Гор Вербински",
        sort_order=118,
    ),
    movie(
        title="Звонок 2",
        genre="Ужасы",
        description="Страшная девочка из колодца вернулась, чтобы отомстить. Рейчел с сыном переезжают в маленький городок, но мстительная Самара вернулась, чтобы продолжить свой террор.",
        duration=110, age=16, year=2005, country="США", director="Хидео Наката",
        sort_order=119,
    ),
    movie(
        title="Супер Марио Брос. 2",
        genre="Мультфильм",
        description="После победы над Боузером и спасения Бруклина Марио сталкивается со злобным альянсом Варио и Боузера-младшего. Вместе с друзьями и Йоши он должен помешать их планам по завоеванию мирового господства.",
        duration=95, age=6, year=2026, country="США",
        sort_order=120,
    ),
    movie(
        title="Тамерлан",
        genre="Историческая драма",
        description="Он объединил земли и обрёл величие, но потерял любовь. XIV век. Закалённый в боях Тимур Барлас возвращается в родные края, чтобы бороться за честь семьи, любовь и будущее своих людей.",
        duration=107, age=16, year=2026, country="Узбекистан",
        sort_order=121,
    ),
    movie(
        title="Вершина",
        genre="Боевик, Триллер",
        description="Экстремалка Саша переживает смерть близкого и отправляется в одиночное путешествие по Австралии. Оказавшись в глуши, она становится целью отморозка, который любит охотиться на людей.",
        duration=95, age=18, year=2026, country="Канада, Австралия, США, Исландия", director="Бальтасар Кормакур",
        cast=["Шарлиз Терон", "Тэрон Эджертон", "Эрик Бана"],
        sort_order=122,
    ),
    movie(
        title="Свет внутри",
        genre="Драма",
        description="Парень с аутизмом и его юный друг едут из Кыргызстана в Москву. Адиль и его девятилетний друг Самир отправляются в полное испытаний путешествие, чтобы исполнить мечту мальчика.",
        duration=95, age=6, year=2025, country="Кыргызстан, Россия",
        sort_order=123,
    ),
    movie(
        title="Олли и Айви",
        genre="Мультфильм",
        description="Маленькое лесное существо Олли и величественная птица Айви, которая охотится на него, волшебным образом меняются телами. Чтобы снова оказаться в своей шкуре, им приходится объединить силы.",
        duration=88, age=6, year=2025, country="",
        sort_order=124,
    ),
    movie(
        title="Дом в аренду",
        genre="Ужасы",
        description="Супруги подозревают, что арендаторы проводят в их доме зловещие ритуалы. Из-за финансовых сложностей семья сдаёт свой дом и переезжает в квартиру, а новые жильцы ведут себя очень подозрительно.",
        duration=124, age=18, year=2023, country="Таиланд",
        sort_order=125,
    ),
    movie(
        title="Дьявол носит Prada 2",
        genre="Драма, Комедия",
        description="Миранда Пристли борется за выживание журнала в эпоху новых медиа, отстаивая рекламные контракты со своей бывшей помощницей Эмили Чарлтон.",
        duration=115, age=16, year=2026, country="США",
        cast=["Мэрил Стрип", "Энн Хэтэуэй"],
        sort_order=126,
    ),
    movie(
        title="Мортал Комбат 2",
        genre="Боевик, Фантастика",
        description="Отставной звезде боевиков суждено стать защитником Земли. Чемпионы Земного царства вместе с Джонни Кейджем вступают в схватку друг с другом, чтобы предотвратить тёмное правление Шао Кана.",
        duration=110, age=18, year=2025, country="США",
        cast=["Карл Урбан"],
        sort_order=127,
    ),
    movie(
        title="Возвращение Кэти",
        genre="Триллер, Драма",
        description="Журналист Чарли Кэннон живёт с семьёй. Однажды дочь Кэти бесследно исчезает. Спустя восемь лет она неожиданно возвращается домой, но вместе с надеждой в жизнь семьи приходит новая тревога.",
        duration=105, age=16, year=2025, country="",
        sort_order=128,
    ),
    movie(
        title="Ла Йорона: Проклятие плачущей",
        genre="Ужасы",
        description="Злой дух из мексиканской легенды охотится на детей в Лос-Анджелесе. Ла Йорона крадется в тени и охотится на детей, отчаянно пытаясь восполнить утрату собственных.",
        duration=93, age=16, year=2019, country="США", director="Майкл Чавес",
        sort_order=129,
    ),
    movie(
        title="Голос за стеной",
        genre="Ужасы",
        description="Родители внушают сыну, что его кошмары — плод воображения. У восьмилетнего Питера нет друзей. Однажды ночью мальчик начинает слышать голос из стены, рассказывающий, что его родители скрывают мрачные тайны.",
        duration=88, age=16, year=2023, country="США",
        cast=["Энтони Старр"],
        sort_order=130,
    ),
    movie(
        title="Dacha",
        genre="Триллер",
        description="Группа молодых людей отправляется за город на дачу отдохнуть. За внешне беззаботным сбором скрываются секреты, грехи и предательства каждого героя. Обычный отдых превращается в психологическое испытание на выживание.",
        duration=95, age=16, year=2025, country="Узбекистан",
        sort_order=131,
    ),
    movie(
        title="Прикосновение тьмы",
        genre="Ужасы",
        description="Дочь парапсихолога помогает девочке, которую преследует демон. Психотерапевт Синтия Уинстоун обладает даром проникать в чужое подсознание, а её дочь Джордан решает помочь напуганной девочке-подростку.",
        duration=98, age=16, year=2025, country="США",
        cast=["Эшли Грин"],
        sort_order=132,
    ),
    movie(
        title="В сером",
        genre="Боевик, Триллер",
        description="Джейк Джилленхол и Генри Кавилл в азартном экшене Гая Ричи. Когда безжалостный магнат Саласар присваивает миллиард долларов, отряд элитных агентов под руководством Рэйчел получает задание вернуть деньги любой ценой.",
        duration=128, age=16, year=2026, country="США", director="Гай Ричи",
        cast=["Генри Кавилл", "Джейк Джилленхол", "Эйза Гонсалес", "Розамунд Пайк"],
        sort_order=133,
    ),
    movie(
        title="Майкл Джексон: История",
        genre="Биография, Музыкальный",
        description="Блокбастер о становлении короля поп-музыки. История жизни короля поп-музыки Майкла Джексона.",
        duration=140, age=16, year=2026, country="США",
        sort_order=134,
    ),
    movie(
        title="Заклятие: Последний обряд",
        genre="Ужасы",
        description="Экзорцисты помогают семье, которую преследует сущность из зеркал. 1986 год. Семейство Смерл покупает старинное зеркало, из-за которого 22 года назад Эд и Лоррейн Уоррены чуть не потеряли новорождённую дочь.",
        duration=135, age=16, year=2025, country="США",
        cast=["Патрик Уилсон", "Вера Фармига"],
        sort_order=135,
    ),
    movie(
        title="Ведьма из отеля",
        genre="Ужасы",
        description="Писатель останавливается в отеле, где, по слухам, обитает ведьма. Американский писатель Ом Бауман приезжает в старую гостиницу в ирландской глуши, где, как сообщается, заперта ведьма.",
        duration=98, age=16, year=2025, country="",
        sort_order=136,
    ),
]


def _install_posters() -> None:
    if not ASSETS_DIR.exists():
        return
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    for payload in CLIENT_MOVIES:
        poster_file = payload.get("_poster_file")
        if not poster_file:
            continue
        src = ASSETS_DIR / poster_file
        dst = UPLOAD_DIR / poster_file
        if src.exists() and not dst.exists():
            shutil.copy(src, dst)


async def add_client_movies() -> None:
    _install_posters()
    created = 0
    skipped = 0
    async with SessionLocal() as session:
        for payload in CLIENT_MOVIES:
            values = {k: v for k, v in payload.items() if not k.startswith("_")}
            exists = await session.scalar(select(Movie.id).where(Movie.title == values["title"]).limit(1))
            if exists is not None:
                skipped += 1
                continue
            session.add(Movie(**values))
            created += 1
        await session.commit()
    print(f"Client movie import complete: created={created}, skipped_existing={skipped}")


if __name__ == "__main__":
    asyncio.run(add_client_movies())
