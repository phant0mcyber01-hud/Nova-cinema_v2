"""Turning Movie and Booking rows into the payloads the clients consume."""
from __future__ import annotations

import json
from datetime import date

from backend.core.config import QR_VALID_STATUSES
from backend.models import Movie, Review
from backend.services.i18n import normalize_language


def is_new_release(movie: Movie, today: str | None = None) -> bool:
    """A movie stays a new release until `new_until` passes (empty = no expiry)."""
    if not movie.is_new:
        return False
    if not movie.new_until:
        return True
    return movie.new_until >= (today or date.today().isoformat())


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


def serialize_movie(
    movie: Movie,
    reviews: list[Review] | None = None,
    language: str = "ru",
    sessions: list[str] | None = None,
) -> dict[str, object]:
    """`sessions` comes from the `shows` table; callers pass it in to avoid N+1."""
    items = [review for review in (reviews if reviews is not None else movie.reviews) if review.approved]
    user_rating = round(sum(item.rating for item in items) / len(items), 1) if items else movie.internal_rating
    text = localized_movie_text(movie, language)
    return {
        "id": movie.id,
        "title": text["title"],
        "genre": text["genre"],
        "description": text["description"],
        "poster": movie.poster,
        "trailer_id": movie.trailer_id,
        "duration": movie.duration,
        "age": movie.age,
        "year": movie.year,
        "country": text["country"],
        "director": text["director"],
        "cast": text["cast"],
        "gallery": json.loads(movie.gallery_json),
        "imdb": movie.imdb,
        "kinopoisk": movie.kinopoisk,
        "sessions": sessions or [],
        "user_rating": user_rating,
        "rating": user_rating or 0,
        "internal_rating": movie.internal_rating,
        "ticket_price": movie.ticket_price,
        "is_published": movie.is_published,
        "is_new": is_new_release(movie),
        "new_until": movie.new_until,
        "sort_order": movie.sort_order,
    }


def serialize_booking(booking, movie: Movie, language: str = "ru") -> dict[str, object]:
    text = localized_movie_text(movie, language)
    return {
        "id": booking.id,
        "uuid": booking.uuid,
        "qr_token": booking.qr_token,
        "qr_valid": booking.status in QR_VALID_STATUSES,
        "movie": text["title"],
        "poster": movie.poster,
        "description": text["description"],
        "trailer_id": movie.trailer_id,
        "show_date": booking.show_date,
        "session": booking.session,
        "seats": booking.seats,
        "seats_count": len([seat for seat in booking.seats.split(",") if seat]),
        "ticket_price": booking.ticket_price,
        "total": booking.total,
        "status": booking.status,
        "phone": booking.phone,
        "telegram_username": booking.telegram_username,
        "comment": booking.comment,
        "proposed_session": booking.proposed_session,
        "admin_note": booking.admin_note,
    }
