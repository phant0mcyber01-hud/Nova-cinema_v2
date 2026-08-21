"""TMDb + OMDb lookup that pre-fills the admin movie form."""
from __future__ import annotations

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
        search = await fetch_json(
            client,
            f"{config.TMDB_BASE_URL}/search/movie",
            {"api_key": config.TMDB_API_KEY, "query": title, "language": "ru-RU", "include_adult": "false"},
        )
        results = search.get("results", [])
        if not isinstance(results, list) or not results:
            raise HTTPException(404, "Movie not found")
        movie_id = results[0].get("id")
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
    imdb = rating_from_omdb(str(omdb.get("imdbRating", "0")))
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
        "kinopoisk": 0,
        "internal_rating": tmdb_rating or None,
        "trailer_id": youtube_from_videos(details.get("videos") if isinstance(details.get("videos"), dict) else {}),
        "poster": tmdb_image(str(details.get("poster_path") or ""), "w780"),
        "gallery": [tmdb_image(str(path), "w1280") for path in gallery_paths],
        "ticket_price": None,
        "is_published": True,
        "sort_order": 0,
    }
