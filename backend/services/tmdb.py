"""TMDb + OMDb lookup that pre-fills the admin movie form."""
from __future__ import annotations

import re
import unicodedata
import xml.etree.ElementTree as ET

import httpx
from fastapi import HTTPException

from backend.core import config
from backend.core.db import utcnow


def tmdb_image(path: str | None, size: str = "w780") -> str:
    return f"{config.TMDB_IMAGE_URL}/{size}{path}" if path else ""


def age_from_releases(releases: dict[str, object]) -> int:
    results = releases.get("results", []) if isinstance(releases, dict) else []
    if not isinstance(results, list):
        return 12
    certificates: list[str] = []
    for country in ("RU", "UZ", "US"):
        for item in results:
            if not isinstance(item, dict) or item.get("iso_3166_1") != country:
                continue
            items = item.get("release_dates", [])
            if isinstance(items, list):
                certificates.extend(str(row.get("certification", "")) for row in items if isinstance(row, dict))
    text = " ".join(certificates).upper()
    if "18" in text or "NC-17" in text or "R" in text:
        return 18
    if "16" in text:
        return 16
    if "13" in text or "PG-13" in text:
        return 13
    if "12" in text:
        return 12
    if "6" in text or "PG" in text:
        return 6
    return 12


def youtube_from_videos(videos: dict[str, object]) -> str:
    results = videos.get("results", []) if isinstance(videos, dict) else []
    if not isinstance(results, list):
        return ""
    youtube = [item for item in results if isinstance(item, dict) and item.get("site") == "YouTube"]
    trailers = [item for item in youtube if str(item.get("type", "")).lower() == "trailer"]
    official = [item for item in trailers if item.get("official")]
    choice = (official or trailers or youtube or [{}])[0]
    return str(choice.get("key", ""))


def rating_from_omdb(value: str) -> float:
    try:
        return round(float(value), 1)
    except ValueError:
        return 0


def _normalized_title(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    return re.sub(r"[^a-zа-яё0-9]+", "", value)


def choose_movie_result(results: list[dict[str, object]], query: str) -> dict[str, object]:
    """Prefer an exact title/year match instead of blindly taking TMDB rank one."""
    year_match = re.search(r"\b(19\d{2}|20\d{2})\b", query)
    wanted_year = year_match.group(1) if year_match else ""
    wanted = _normalized_title(re.sub(r"\b(19\d{2}|20\d{2})\b", "", query))

    def score(item: dict[str, object]) -> tuple[int, int, int]:
        names = [_normalized_title(str(item.get(key) or "")) for key in ("title", "original_title")]
        exact = 2 if wanted and wanted in names else 1 if wanted and any(wanted in name or name in wanted for name in names) else 0
        released = str(item.get("release_date") or "")[:4]
        year_score = 2 if wanted_year and released == wanted_year else 0 if not wanted_year else -2
        try:
            votes = int(item.get("vote_count") or 0)
        except (TypeError, ValueError):
            votes = 0
        return exact, year_score, votes

    return max(results, key=score)


def kinopoisk_id_from_wikidata(payload: dict[str, object], qid: str) -> str:
    try:
        claims = payload["entities"][qid]["claims"]  # type: ignore[index]
        return str(claims["P2603"][0]["mainsnak"]["datavalue"]["value"])  # type: ignore[index]
    except (KeyError, IndexError, TypeError):
        return ""


def rating_from_kinopoisk_xml(content: bytes) -> float:
    try:
        value = ET.fromstring(content).findtext("kp_rating") or ""
        return round(float(value), 1) if value else 0
    except (ET.ParseError, ValueError):
        return 0


async def external_ratings(
    client: httpx.AsyncClient, imdb_id: str, wikidata_id: str, omdb: dict[str, object]
) -> tuple[float, float]:
    """Fetch real IMDb/KP ratings through public datasets; failures stay non-fatal."""
    imdb = rating_from_omdb(str(omdb.get("imdbRating", "0")))
    kinopoisk = 0.0
    if not imdb and imdb_id:
        try:
            response = await client.get(
                "https://api.agregarr.org/api/ratings",
                params=[("id", imdb_id)],
                headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
            )
            if response.status_code == 200:
                rows = response.json()
                if isinstance(rows, list) and rows and isinstance(rows[0], dict) and rows[0].get("rating") is not None:
                    imdb = round(float(rows[0]["rating"]), 1)
        except (httpx.HTTPError, ValueError, TypeError, KeyError):
            pass
    if wikidata_id:
        try:
            response = await client.get(
                f"https://www.wikidata.org/wiki/Special:EntityData/{wikidata_id}.json",
                headers={"User-Agent": "NovaCinema/1.0"},
            )
            kp_id = kinopoisk_id_from_wikidata(response.json(), wikidata_id) if response.status_code == 200 else ""
            if kp_id:
                rating_response = await client.get(
                    f"https://rating.kinopoisk.ru/{kp_id}.xml",
                    headers={"User-Agent": "Mozilla/5.0"},
                )
                if rating_response.status_code == 200:
                    kinopoisk = rating_from_kinopoisk_xml(rating_response.content)
        except (httpx.HTTPError, ValueError, TypeError, KeyError):
            pass
    return imdb, kinopoisk


async def fetch_json(client: httpx.AsyncClient, url: str, params: dict[str, object]) -> dict[str, object]:
    try:
        response = await client.get(url, params=params)
    except httpx.HTTPError as error:
        raise HTTPException(502, "Movie API is unavailable") from error
    if response.status_code == 401:
        raise HTTPException(503, "Movie API key is invalid")
    if response.status_code == 404:
        raise HTTPException(404, "Movie not found")
    if response.status_code >= 400:
        raise HTTPException(502, "Movie API request failed")
    data = response.json()
    return data if isinstance(data, dict) else {}


async def lookup_movie_payload(title: str) -> dict[str, object]:
    if not config.TMDB_API_KEY:
        raise HTTPException(503, "TMDB_API_KEY is not configured")
    async with httpx.AsyncClient(timeout=12) as client:
        year_match = re.search(r"\b(19\d{2}|20\d{2})\b", title)
        search_title = re.sub(r"\b(19\d{2}|20\d{2})\b", "", title).strip()
        search_params: dict[str, object] = {
            "api_key": config.TMDB_API_KEY,
            "query": search_title,
            "language": "ru-RU",
            "include_adult": "false",
        }
        if year_match:
            search_params["year"] = int(year_match.group(1))
        search = await fetch_json(
            client,
            f"{config.TMDB_BASE_URL}/search/movie",
            search_params,
        )
        results = search.get("results", [])
        if not isinstance(results, list) or not results:
            raise HTTPException(404, "Movie not found")
        valid_results = [row for row in results if isinstance(row, dict)]
        if not valid_results:
            raise HTTPException(404, "Movie not found")
        selected = choose_movie_result(valid_results, title)
        movie_id = selected.get("id")
        if not movie_id:
            raise HTTPException(404, "Movie not found")
        details = await fetch_json(
            client,
            f"{config.TMDB_BASE_URL}/movie/{movie_id}",
            {
                "api_key": config.TMDB_API_KEY,
                "language": "ru-RU",
                "append_to_response": "credits,images,videos,external_ids,release_dates",
                "include_image_language": "ru,en,null",
            },
        )
        imdb_id = str((details.get("external_ids") or {}).get("imdb_id") or "")
        omdb: dict[str, object] = {}
        if config.OMDB_API_KEY and imdb_id:
            omdb = await fetch_json(
                client, config.OMDB_BASE_URL, {"apikey": config.OMDB_API_KEY, "i": imdb_id, "plot": "full"}
            )
        wikidata_id = str((details.get("external_ids") or {}).get("wikidata_id") or "")
        imdb, kinopoisk = await external_ratings(client, imdb_id, wikidata_id, omdb)

    credits = details.get("credits") if isinstance(details.get("credits"), dict) else {}
    crew = credits.get("crew", []) if isinstance(credits, dict) else []
    cast_items = credits.get("cast", []) if isinstance(credits, dict) else []
    director = next(
        (str(item.get("name", "")) for item in crew if isinstance(item, dict) and item.get("job") == "Director"), ""
    )
    cast = [str(item.get("name", "")) for item in cast_items[:8] if isinstance(item, dict) and item.get("name")]
    countries = details.get("production_countries", [])
    genres = details.get("genres", [])
    images = details.get("images") if isinstance(details.get("images"), dict) else {}
    backdrops = images.get("backdrops", []) if isinstance(images, dict) else []
    posters = images.get("posters", []) if isinstance(images, dict) else []
    gallery_paths = [
        item.get("file_path") for item in [*backdrops[:6], *posters[:3]] if isinstance(item, dict) and item.get("file_path")
    ]
    release_date = str(details.get("release_date", ""))
    description = str(details.get("overview") or omdb.get("Plot") or "")
    tmdb_rating = round(float(details.get("vote_average") or 0), 1)
    return {
        "title": str(details.get("title") or details.get("original_title") or title),
        "description": description,
        "genre": ", ".join(str(item.get("name", "")) for item in genres if isinstance(item, dict) and item.get("name")),
        "country": ", ".join(
            str(item.get("name", "")) for item in countries if isinstance(item, dict) and item.get("name")
        ),
        "year": int(release_date[:4]) if release_date[:4].isdigit() else utcnow().year,
        "duration": int(details.get("runtime") or 90),
        "age": age_from_releases(details.get("release_dates") if isinstance(details.get("release_dates"), dict) else {}),
        "director": director,
        "cast": cast,
        "imdb": imdb,
        "kinopoisk": kinopoisk,
        "internal_rating": tmdb_rating or None,
        "trailer_id": youtube_from_videos(details.get("videos") if isinstance(details.get("videos"), dict) else {}),
        "poster": tmdb_image(str(details.get("poster_path") or ""), "w780"),
        "gallery": [tmdb_image(str(path), "w1280") for path in gallery_paths],
        "ticket_price": None,
        "is_published": True,
        "sort_order": 0,
        "audio_languages": ["ru", "uz"],
    }
