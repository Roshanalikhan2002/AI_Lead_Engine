from __future__ import annotations

from app.models.lead import Lead
from app.services.place_types import PlaceBusiness
from app.utils.normalize import normalize_domain, normalize_phone


def passes_filters(
    business: PlaceBusiness,
    *,
    min_rating: float | None,
    min_reviews: int | None,
    website_filter: str,
) -> bool:
    if min_rating is not None and (business.rating is None or business.rating < min_rating):
        return False
    if min_reviews is not None and (business.review_count is None or business.review_count < min_reviews):
        return False

    has_website = bool(business.website and business.website.strip())
    if website_filter == "yes" and not has_website:
        return False
    if website_filter == "no" and has_website:
        return False
    return True


def to_lead(
    business: PlaceBusiness,
    *,
    industry: str,
    organization_id,
    generation_job_id=None,
    source: str = "google_places",
) -> Lead:
    return Lead(
        organization_id=organization_id,
        external_id=business.google_place_id,
        company_name=business.company_name,
        industry=industry,
        country=business.country,
        state=business.state,
        city=business.city,
        address=business.address,
        phone=business.phone,
        website=business.website,
        google_place_id=business.google_place_id,
        google_maps_url=business.google_maps_url,
        rating=business.rating,
        review_count=business.review_count,
        business_status=business.business_status,
        latitude=business.latitude,
        longitude=business.longitude,
        source=source,
        normalized_phone=normalize_phone(business.phone),
        normalized_domain=normalize_domain(business.website),
        generation_job_id=generation_job_id,
    )
