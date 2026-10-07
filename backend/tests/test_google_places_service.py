"""GooglePlacesService offline tests — HTTP mocked; no live Google calls."""

from __future__ import annotations

import httpx
import pytest

from app.core.config import Settings
from app.services.google_places import GooglePlacesError, GooglePlacesService, PLACES_TEXT_SEARCH_URL
from app.services.offline_places_fixture import OFFLINE_PLACES, offline_places_page


def _settings(**kwargs) -> Settings:
    base = {
        "GOOGLE_PLACES_API_KEY": "test-key-not-real",
        "GOOGLE_PLACES_MOCK": "false",
        "places_request_delay_seconds": 0,
    }
    base.update(kwargs)
    return Settings(**base)


class _FakeResponse:
    def __init__(self, status_code: int, payload=None, text: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = text or ("" if payload is None else str(payload))

    def json(self):
        if self._payload is None:
            raise ValueError("invalid json")
        return self._payload


class _FakeClient:
    def __init__(self, handler):
        self.handler = handler
        self.calls: list[dict] = []

    def post(self, url, headers=None, json=None):
        self.calls.append({"url": url, "headers": headers, "json": json})
        return self.handler(url, headers, json)

    def close(self):
        pass


def test_build_text_query_prefers_keywords():
    service = GooglePlacesService(_settings())
    assert (
        service.build_text_query(
            industry="Dental Clinics",
            keywords="dentist",
            city="Houston",
            state="Texas",
            country="USA",
        )
        == "dentist in Houston, Texas, USA"
    )


def test_build_text_query_falls_back_to_industry():
    service = GooglePlacesService(_settings())
    assert (
        service.build_text_query(
            industry="Hotels",
            keywords=None,
            city="Houston",
            state="Texas",
            country="USA",
        )
        == "Hotels in Houston, Texas, USA"
    )


def test_search_parses_missing_optional_fields(zero_places_delay):
    page = {"places": [OFFLINE_PLACES[2], OFFLINE_PLACES[4], OFFLINE_PLACES[6]]}

    def handler(_url, _headers, _body):
        return _FakeResponse(200, page)

    client = _FakeClient(handler)
    with GooglePlacesService(_settings(), client=client) as service:
        results = service.search_businesses(
            industry="Dental Clinics",
            keywords="dentist",
            city="Houston",
            state="Texas",
            country="USA",
            min_rating=None,
            quantity=10,
        )

    assert len(results) == 3
    no_website = next(r for r in results if r.google_place_id == "ChIJmockDental003")
    assert no_website.website is None
    assert no_website.phone is not None

    no_phone = next(r for r in results if r.google_place_id == "ChIJmockRest002")
    assert no_phone.phone is None
    assert no_phone.website is not None

    no_rating = next(r for r in results if r.google_place_id == "ChIJmockHotel002")
    assert no_rating.rating is None
    assert no_rating.review_count is None


def test_search_request_construction(zero_places_delay):
    def handler(url, headers, body):
        assert url == PLACES_TEXT_SEARCH_URL
        assert headers["X-Goog-Api-Key"] == "test-key-not-real"
        assert "places.id" in headers["X-Goog-FieldMask"]
        assert body["textQuery"] == "dentist in Houston, Texas, USA"
        assert body["regionCode"] == "US"
        assert body["minRating"] == 4.0
        return _FakeResponse(200, {"places": OFFLINE_PLACES[:2]})

    client = _FakeClient(handler)
    with GooglePlacesService(_settings(), client=client) as service:
        results = service.search_businesses(
            industry="Dental Clinics",
            keywords="dentist",
            city="Houston",
            state="Texas",
            country="USA",
            min_rating=4.0,
            quantity=2,
        )
    assert len(results) == 2
    assert len(client.calls) == 1


def test_pagination_and_duplicate_place_ids(zero_places_delay):
    def handler(_url, _headers, body):
        token = body.get("pageToken")
        return _FakeResponse(200, offline_places_page(page_token=token, include_duplicate_id=True))

    client = _FakeClient(handler)
    with GooglePlacesService(_settings(places_page_size=20, places_max_pages=5), client=client) as service:
        results = service.search_businesses(
            industry="Mixed",
            keywords="business",
            city="Houston",
            state="Texas",
            country="USA",
            min_rating=None,
            quantity=20,
        )

    ids = [r.google_place_id for r in results]
    assert len(ids) == len(set(ids))
    assert "ChIJmockDental001" in ids
    assert len(client.calls) == 2
    assert client.calls[1]["json"]["pageToken"] == "offline-page-2"


def test_auth_error(zero_places_delay):
    client = _FakeClient(lambda *_a: _FakeResponse(403, text="forbidden"))
    with GooglePlacesService(_settings(), client=client) as service:
        with pytest.raises(GooglePlacesError) as exc:
            service.search_businesses(
                industry="Dental Clinics",
                keywords="dentist",
                city="Houston",
                state="Texas",
                country="USA",
                min_rating=None,
                quantity=5,
            )
    assert "authentication" in str(exc.value).lower()
    assert "test-key-not-real" not in str(exc.value)


def test_rate_limit_error(zero_places_delay):
    client = _FakeClient(lambda *_a: _FakeResponse(429, text="rate"))
    with GooglePlacesService(_settings(), client=client) as service:
        with pytest.raises(GooglePlacesError) as exc:
            service.search_businesses(
                industry="Dental Clinics",
                keywords="dentist",
                city="Houston",
                state="Texas",
                country="USA",
                min_rating=None,
                quantity=5,
            )
    assert exc.value.status_code == 429


def test_network_error(zero_places_delay):
    class BoomClient:
        def post(self, *args, **kwargs):
            raise httpx.ConnectError("connection failed")

        def close(self):
            pass

    with GooglePlacesService(_settings(), client=BoomClient()) as service:
        with pytest.raises(GooglePlacesError) as exc:
            service.search_businesses(
                industry="Dental Clinics",
                keywords="dentist",
                city="Houston",
                state="Texas",
                country="USA",
                min_rating=None,
                quantity=5,
            )
    assert "Unable to reach Google Places" in str(exc.value)


def test_malformed_json_response(zero_places_delay):
    client = _FakeClient(lambda *_a: _FakeResponse(200, payload=None, text="not-json"))
    with GooglePlacesService(_settings(), client=client) as service:
        with pytest.raises(GooglePlacesError) as exc:
            service.search_businesses(
                industry="Dental Clinics",
                keywords="dentist",
                city="Houston",
                state="Texas",
                country="USA",
                min_rating=None,
                quantity=5,
            )
    assert "Malformed" in str(exc.value)


def test_malformed_places_not_list(zero_places_delay):
    client = _FakeClient(lambda *_a: _FakeResponse(200, {"places": "oops"}))
    with GooglePlacesService(_settings(), client=client) as service:
        with pytest.raises(GooglePlacesError) as exc:
            service.search_businesses(
                industry="Dental Clinics",
                keywords="dentist",
                city="Houston",
                state="Texas",
                country="USA",
                min_rating=None,
                quantity=5,
            )
    assert "places must be a list" in str(exc.value)


def test_missing_api_key_raises_clean_error():
    with GooglePlacesService(_settings(GOOGLE_PLACES_API_KEY="")) as service:
        with pytest.raises(GooglePlacesError) as exc:
            service.search_businesses(
                industry="Dental Clinics",
                keywords="dentist",
                city="Houston",
                state="Texas",
                country="USA",
                min_rating=None,
                quantity=5,
            )
    assert "GOOGLE_PLACES_API_KEY" in str(exc.value)


def test_offline_mock_mode_uses_fixture_without_http(zero_places_delay):
    class MustNotCall:
        def post(self, *args, **kwargs):
            raise AssertionError("HTTP must not be called in mock mode")

        def close(self):
            pass

    settings = _settings(GOOGLE_PLACES_MOCK="true", GOOGLE_PLACES_API_KEY="")
    with GooglePlacesService(settings, client=MustNotCall()) as service:
        results = service.search_businesses(
            industry="Dental Clinics",
            keywords="dentist",
            city="Houston",
            state="Texas",
            country="USA",
            min_rating=None,
            quantity=10,
        )
    assert len(results) == 10
    assert all(r.company_name for r in results)
