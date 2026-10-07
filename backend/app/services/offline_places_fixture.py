"""
Offline Google Places fixture data.

Used ONLY by:
  - automated tests
  - explicit GOOGLE_PLACES_MOCK=true local QA

Never enabled by default. Live Google Places is used when the mock flag is off.
"""

from __future__ import annotations

from typing import Any


def _place(
    *,
    place_id: str,
    name: str,
    address: str,
    city: str = "Houston",
    state: str = "Texas",
    country: str = "United States",
    phone: str | None = None,
    website: str | None = None,
    rating: float | None = None,
    reviews: int | None = None,
    lat: float = 29.7604,
    lng: float = -95.3698,
    status: str = "OPERATIONAL",
) -> dict[str, Any]:
    place: dict[str, Any] = {
        "id": place_id,
        "displayName": {"text": name, "languageCode": "en"},
        "formattedAddress": address,
        "googleMapsUri": f"https://maps.google.com/?cid={place_id}",
        "businessStatus": status,
        "location": {"latitude": lat, "longitude": lng},
        "addressComponents": [
            {"longText": city, "shortText": city, "types": ["locality"]},
            {"longText": state, "shortText": "TX", "types": ["administrative_area_level_1"]},
            {"longText": country, "shortText": "US", "types": ["country"]},
        ],
    }
    if phone is not None:
        place["nationalPhoneNumber"] = phone
    if website is not None:
        place["websiteUri"] = website
    if rating is not None:
        place["rating"] = rating
    if reviews is not None:
        place["userRatingCount"] = reviews
    return place


# 10 realistic businesses across industries; includes incomplete optional fields.
OFFLINE_PLACES: list[dict[str, Any]] = [
    _place(
        place_id="ChIJmockDental001",
        name="Houston Smile Dental",
        address="100 Main St, Houston, TX 77002, USA",
        phone="(713) 555-0101",
        website="https://www.houstonsmile.com",
        rating=4.8,
        reviews=210,
    ),
    _place(
        place_id="ChIJmockDental002",
        name="Bayou City Orthodontics",
        address="220 Westheimer Rd, Houston, TX 77006, USA",
        phone="(713) 555-0102",
        website="https://bayouortho.com",
        rating=4.5,
        reviews=88,
        lat=29.7430,
        lng=-95.3920,
    ),
    _place(
        place_id="ChIJmockDental003",
        name="Neighborhood Family Dentistry",
        address="45 Shepherd Dr, Houston, TX 77007, USA",
        phone="(713) 555-0103",
        # no website
        rating=4.2,
        reviews=45,
    ),
    _place(
        place_id="ChIJmockRest001",
        name="Gulf Coast Grill",
        address="800 Congress Ave, Houston, TX 77002, USA",
        phone="(713) 555-0201",
        website="https://gulfcoastgrill.example",
        rating=4.6,
        reviews=320,
    ),
    _place(
        place_id="ChIJmockRest002",
        name="Quiet Corner Cafe",
        address="12 Travis St, Houston, TX 77002, USA",
        # no phone
        website="https://quietcorner.example",
        rating=3.4,
        reviews=12,
    ),
    _place(
        place_id="ChIJmockHotel001",
        name="Downtown Houston Inn",
        address="901 Texas Ave, Houston, TX 77002, USA",
        phone="(713) 555-0301",
        website="https://downtownhoustoninn.example",
        rating=4.1,
        reviews=540,
    ),
    _place(
        place_id="ChIJmockHotel002",
        name="Budget Stay Suites",
        address="4100 I-45, Houston, TX 77022, USA",
        phone="(713) 555-0302",
        website="https://budgetstaysuites.example",
        # no rating / reviews
    ),
    _place(
        place_id="ChIJmockRealty001",
        name="Lone Star Realty Group",
        address="500 Louisiana St, Houston, TX 77002, USA",
        phone="(713) 555-0401",
        website="https://www.lonestarrealty.example",
        rating=4.9,
        reviews=76,
    ),
    _place(
        place_id="ChIJmockRealty002",
        name="River Oaks Homes",
        address="2200 Kirby Dr, Houston, TX 77019, USA",
        phone="(713) 555-0402",
        # no website, low rating
        rating=2.8,
        reviews=9,
    ),
    _place(
        place_id="ChIJmockDentalDup",
        name="Duplicate Smile Dental",
        address="100 Main St Dup, Houston, TX 77002, USA",
        phone="(713) 555-0199",
        website="https://dup.houstonsmile.com",
        rating=4.0,
        reviews=25,
    ),
]

# Intentional duplicate of first place id (pagination / API quirks).
DUPLICATE_PLACE_COPY = _place(
    place_id="ChIJmockDental001",
    name="Houston Smile Dental (Duplicate ID)",
    address="100 Main St, Houston, TX 77002, USA",
    phone="(713) 555-0101",
    website="https://www.houstonsmile.com",
    rating=4.8,
    reviews=210,
)


def offline_places_page(
    *,
    page_token: str | None = None,
    include_duplicate_id: bool = False,
) -> dict[str, Any]:
    """Simulate Places Text Search pagination over the offline fixture."""
    page1 = list(OFFLINE_PLACES[:5])
    if include_duplicate_id:
        page1 = page1 + [DUPLICATE_PLACE_COPY]
    page2 = list(OFFLINE_PLACES[5:])

    if page_token == "offline-page-2":
        return {"places": page2}
    return {"places": page1, "nextPageToken": "offline-page-2"}


def all_offline_places(*, include_duplicate_id: bool = False) -> list[dict[str, Any]]:
    places = list(OFFLINE_PLACES)
    if include_duplicate_id:
        places.append(DUPLICATE_PLACE_COPY)
    return places
