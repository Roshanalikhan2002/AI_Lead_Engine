from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PlaceBusiness:
    google_place_id: str | None
    company_name: str
    address: str | None = None
    phone: str | None = None
    website: str | None = None
    rating: float | None = None
    review_count: int | None = None
    google_maps_url: str | None = None
    business_status: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
