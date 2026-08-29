import httpx
import pytest
from fastapi import HTTPException

from backend.core import config
from backend.services import tmdb


def test_movie_lookup_prefers_exact_title_and_requested_year():
    results = [
        {"id": 680493, "title": "Возвращение в Сайлент Хилл", "original_title": "Return to Silent Hill", "release_date": "2026-01-21", "vote_count": 800},
        {"id": 588, "title": "Сайлент Хилл", "original_title": "Silent Hill", "release_date": "2006-04-21", "vote_count": 5000},
    ]
    assert tmdb.choose_movie_result(results, "Silent Hill 2006")["id"] == 588
    assert tmdb.choose_movie_result(results, "Silent Hill")["id"] == 588


def test_movie_lookup_tolerates_malformed_vote_count():
    results = [
        {"id": 588, "title": "Сайлент Хилл", "original_title": "Silent Hill", "release_date": "2006-04-21", "vote_count": "unknown"},
    ]
    assert tmdb.choose_movie_result(results, "Silent Hill 2006")["id"] == 588


def test_kinopoisk_rating_xml_is_parsed_without_rounding_to_zero():
    xml = b'<?xml version="1.0"?><rating><kp_rating num_vote="100">8.682</kp_rating><imdb_rating>8.8</imdb_rating></rating>'
    assert tmdb.rating_from_kinopoisk_xml(xml) == 8.7


def test_wikidata_kinopoisk_id_is_read_from_p2603():
    payload = {"entities": {"Q1": {"claims": {"P2603": [{"mainsnak": {"datavalue": {"value": "361"}}}]}}}}
    assert tmdb.kinopoisk_id_from_wikidata(payload, "Q1") == "361"


@pytest.mark.asyncio
async def test_external_ratings_ignores_malformed_agregarr_rows():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=["malformed"])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert await tmdb.external_ratings(client, "tt0137523", "", {}) == (0, 0)


@pytest.mark.asyncio
async def test_lookup_returns_404_when_tmdb_results_contain_no_objects(monkeypatch):
    monkeypatch.setattr(config, "TMDB_API_KEY", "test-key")

    async def fake_fetch(*_args, **_kwargs):
        return {"results": [None, "malformed"]}

    monkeypatch.setattr(tmdb, "fetch_json", fake_fetch)
    with pytest.raises(HTTPException) as error:
        await tmdb.lookup_movie_payload("Silent Hill 2006")
    assert error.value.status_code == 404
