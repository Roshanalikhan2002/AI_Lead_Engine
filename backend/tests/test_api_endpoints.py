"""API endpoint tests using offline mocked Google Places (no live network)."""

from __future__ import annotations

import uuid

import pytest

from app.core.config import Settings, get_settings
from app.models.lead import Lead
from app.services.google_places import GooglePlacesError


FIND_LEADS_PAYLOAD = {
    "country": "USA",
    "state": "Texas",
    "city": "Houston",
    "industry": "Dental Clinics",
    "keywords": "dentist",
    "min_rating": 4.0,
    "min_reviews": 20,
    "website_filter": "any",
    "quantity": 5,
}


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"


@pytest.mark.parametrize(
    "payload,fragment",
    [
        ({**FIND_LEADS_PAYLOAD, "country": ""}, "country"),
        ({**FIND_LEADS_PAYLOAD, "industry": "  "}, "industry"),
        ({**FIND_LEADS_PAYLOAD, "quantity": 0}, "quantity"),
        ({**FIND_LEADS_PAYLOAD, "quantity": 5001}, "quantity"),
        ({**FIND_LEADS_PAYLOAD, "min_rating": -1}, "min_rating"),
        ({**FIND_LEADS_PAYLOAD, "min_rating": 5.1}, "min_rating"),
        ({**FIND_LEADS_PAYLOAD, "min_reviews": -5}, "min_reviews"),
    ],
)
def test_generation_validation_errors(client, payload, fragment):
    response = client.post("/api/generation", json=payload)
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert isinstance(detail, list)
    fields = " ".join(str(item.get("loc", [])) for item in detail).lower()
    assert fragment in fields


def test_find_leads_flow_offline_mock(
    client,
    SessionLocal,
    monkeypatch,
    mock_places_settings,
    zero_places_delay,
):
    """Mirrors frontend Find Leads → poll → list → detail using offline Places."""
    monkeypatch.setattr("app.services.lead_discovery.get_settings", lambda: mock_places_settings)

    created = client.post("/api/generation", json=FIND_LEADS_PAYLOAD)
    assert created.status_code == 202
    data = created.json()
    assert data["status"] == "pending"
    job_id = data["job_id"]

    status = client.get(f"/api/generation/{job_id}")
    assert status.status_code == 200
    body = status.json()
    assert body["status"] == "completed"
    assert body["target"] == 5
    assert body["progress"] == 100
    assert body["found"] >= 1
    assert body["saved"] >= 1
    assert body["error_message"] is None

    listed = client.get("/api/leads?page=1&limit=25&source=google_places_mock&sort=newest")
    assert listed.status_code == 200
    payload = listed.json()
    assert payload["total"] == body["saved"]
    assert payload["page"] == 1
    assert payload["limit"] == 25
    assert payload["pages"] >= 1
    assert len(payload["items"]) == body["saved"]
    for item in payload["items"]:
        assert item["source"] == "google_places_mock"
        assert "google_place_id" in item
        assert item["company_name"]

    lead_id = payload["items"][0]["id"]
    detail = client.get(f"/api/leads/{lead_id}")
    assert detail.status_code == 200
    assert detail.json()["id"] == lead_id
    assert detail.json()["city"]


def test_generation_job_failed_lifecycle(client, SessionLocal, monkeypatch):
    class BoomPlaces:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def search_businesses(self, **kwargs):
            raise GooglePlacesError("Google Places rate limit exceeded. Please try again shortly.", 429)

    monkeypatch.setattr("app.services.lead_discovery.GooglePlacesService", lambda _s: BoomPlaces())
    monkeypatch.setattr(
        "app.services.lead_discovery.get_settings",
        lambda: Settings(GOOGLE_PLACES_API_KEY="x", GOOGLE_PLACES_MOCK="false"),
    )

    created = client.post("/api/generation", json=FIND_LEADS_PAYLOAD)
    assert created.status_code == 202
    job_id = created.json()["job_id"]

    status = client.get(f"/api/generation/{job_id}")
    assert status.status_code == 200
    body = status.json()
    assert body["status"] == "failed"
    assert "rate limit" in (body["error_message"] or "").lower()
    assert body["progress"] < 100 or body["status"] == "failed"


def test_leads_pagination_filter_sort(client, db_session):
    for i in range(3):
        db_session.add(
            Lead(
                id=uuid.uuid4(),
                company_name=f"Alpha Clinic {i}",
                industry="Dental Clinics",
                country="USA",
                state="Texas",
                city="Houston",
                website="https://example.com" if i % 2 == 0 else None,
                google_place_id=f"place-page-{i}",
                rating=4.0 + i * 0.1,
                review_count=30 + i,
                source="google_places_mock",
            )
        )
    db_session.commit()

    page1 = client.get("/api/leads?page=1&limit=2&sort=name")
    assert page1.status_code == 200
    body = page1.json()
    assert body["total"] == 3
    assert body["pages"] == 2
    assert len(body["items"]) == 2

    filtered = client.get("/api/leads?website_filter=yes&country=USA")
    assert filtered.status_code == 200
    assert all(item["website"] for item in filtered.json()["items"])

    missing = client.get(f"/api/leads/{uuid.uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Lead not found"

    unknown_job = client.get(f"/api/generation/{uuid.uuid4()}")
    assert unknown_job.status_code == 404


def test_generation_pending_progress_when_background_skipped(client, monkeypatch):
    monkeypatch.setattr("app.api.routes.generation.run_generation_job", lambda _job_id: None)
    created = client.post("/api/generation", json=FIND_LEADS_PAYLOAD)
    assert created.status_code == 202
    job_id = created.json()["job_id"]
    status = client.get(f"/api/generation/{job_id}")
    assert status.status_code == 200
    assert status.json()["status"] == "pending"
    assert status.json()["progress"] == 0
