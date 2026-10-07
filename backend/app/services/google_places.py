from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from app.core.config import Settings
from app.services.place_types import PlaceBusiness

logger = logging.getLogger(__name__)

PLACES_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.nationalPhoneNumber",
        "places.internationalPhoneNumber",
        "places.websiteUri",
        "places.rating",
        "places.userRatingCount",
        "places.googleMapsUri",
        "places.businessStatus",
        "places.location",
        "places.addressComponents",
        "nextPageToken",
    ]
)

COUNTRY_REGION_CODES = {
    "USA": "US",
    "United States": "US",
    "Canada": "CA",
    "UK": "GB",
    "United Kingdom": "GB",
    "Australia": "AU",
    "Germany": "DE",
    "UAE": "AE",
    "United Arab Emirates": "AE",
}


class GooglePlacesError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class GooglePlacesService:
    def __init__(self, settings: Settings, client: httpx.Client | None = None):
        self.settings = settings
        self._client = client
        self._owns_client = client is None

    def __enter__(self) -> GooglePlacesService:
        if self._client is None:
            self._client = httpx.Client(timeout=30.0)
        return self

    def __exit__(self, *args: object) -> None:
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None

    def build_text_query(
        self,
        *,
        industry: str,
        keywords: str | None,
        city: str,
        state: str | None,
        country: str,
    ) -> str:
        term = (keywords or "").strip() or industry.strip()
        location_parts = [city.strip()]
        if state and state.strip():
            location_parts.append(state.strip())
        location_parts.append(country.strip())
        location = ", ".join(location_parts)
        return f"{term} in {location}"

    def search_businesses(
        self,
        *,
        industry: str,
        keywords: str | None,
        city: str,
        state: str | None,
        country: str,
        min_rating: float | None,
        quantity: int,
    ) -> list[PlaceBusiness]:
        try:
            api_key = self.settings.require_places_key()
        except RuntimeError as exc:
            raise GooglePlacesError(str(exc), 503) from exc

        text_query = self.build_text_query(
            industry=industry,
            keywords=keywords,
            city=city,
            state=state,
            country=country,
        )
        if self.settings.google_places_mock:
            logger.warning(
                "GOOGLE_PLACES_MOCK=true — offline fixture search (not live Google). query=%s",
                text_query,
            )
        else:
            logger.info("Places search query: %s (target=%s)", text_query, quantity)

        collected: list[PlaceBusiness] = []
        seen_ids: set[str] = set()
        page_token: str | None = None
        pages = 0
        max_pages = min(self.settings.places_max_pages, max(1, (quantity + 19) // 20 + 1))

        while len(collected) < quantity and pages < max_pages:
            body: dict[str, Any] = {
                "textQuery": text_query,
                "pageSize": min(20, self.settings.places_page_size),
                "languageCode": "en",
            }
            region = COUNTRY_REGION_CODES.get(country.strip())
            if region:
                body["regionCode"] = region
            if min_rating is not None and min_rating > 0:
                body["minRating"] = min_rating
            if page_token:
                body["pageToken"] = page_token

            payload = self._post_search(api_key, body)
            places = payload.get("places") or []
            if not isinstance(places, list):
                raise GooglePlacesError("Malformed Google Places response: places must be a list.", 502)

            for place in places:
                if not isinstance(place, dict):
                    continue
                business = self._map_place(place, fallback_city=city, fallback_state=state, fallback_country=country)
                place_id = business.google_place_id
                if place_id and place_id in seen_ids:
                    continue
                if place_id:
                    seen_ids.add(place_id)
                collected.append(business)
                if len(collected) >= quantity:
                    break

            pages += 1
            page_token = payload.get("nextPageToken")
            if not page_token or not places:
                break
            time.sleep(self.settings.places_request_delay_seconds)

        logger.info("Places discovered %s businesses for query", len(collected))
        return collected[:quantity]

    def _post_search(self, api_key: str, body: dict[str, Any]) -> dict[str, Any]:
        if self.settings.google_places_mock:
            from app.services.offline_places_fixture import offline_places_page

            return offline_places_page(page_token=body.get("pageToken"), include_duplicate_id=True)

        if self._client is None:
            raise GooglePlacesError("HTTP client is not initialized")

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": FIELD_MASK,
        }
        try:
            response = self._client.post(PLACES_TEXT_SEARCH_URL, headers=headers, json=body)
        except httpx.HTTPError as exc:
            raise GooglePlacesError(
                "Unable to reach Google Places. Check network connectivity and try again.",
                None,
            ) from exc

        if response.status_code == 429:
            raise GooglePlacesError("Google Places rate limit exceeded. Please try again shortly.", 429)
        if response.status_code in {401, 403}:
            raise GooglePlacesError(
                "Google Places authentication failed. Check GOOGLE_PLACES_API_KEY and API permissions.",
                response.status_code,
            )
        if response.status_code >= 400:
            raise GooglePlacesError(
                f"Google Places request failed ({response.status_code}).",
                response.status_code,
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise GooglePlacesError("Malformed Google Places response: invalid JSON.", 502) from exc

        if not isinstance(payload, dict):
            raise GooglePlacesError("Malformed Google Places response: expected an object.", 502)
        return payload

    def _map_place(
        self,
        place: dict[str, Any],
        *,
        fallback_city: str,
        fallback_state: str | None,
        fallback_country: str,
    ) -> PlaceBusiness:
        display = place.get("displayName") or {}
        location = place.get("location") or {}
        components = place.get("addressComponents") or []
        city, state, country = self._parse_address_components(components)

        return PlaceBusiness(
            google_place_id=place.get("id"),
            company_name=(display.get("text") or "Unknown Business").strip(),
            address=place.get("formattedAddress"),
            phone=place.get("nationalPhoneNumber") or place.get("internationalPhoneNumber"),
            website=place.get("websiteUri"),
            rating=place.get("rating"),
            review_count=place.get("userRatingCount"),
            google_maps_url=place.get("googleMapsUri"),
            business_status=place.get("businessStatus"),
            latitude=location.get("latitude"),
            longitude=location.get("longitude"),
            city=city or fallback_city,
            state=state or fallback_state,
            country=country or fallback_country,
        )

    def _parse_address_components(self, components: list[dict[str, Any]]) -> tuple[str | None, str | None, str | None]:
        city = None
        state = None
        country = None
        for component in components:
            types = set(component.get("types") or [])
            text = component.get("longText") or component.get("shortText")
            if not text:
                continue
            if "locality" in types or "postal_town" in types:
                city = text
            elif "administrative_area_level_1" in types:
                state = text
            elif "country" in types:
                country = text
        return city, state, country
