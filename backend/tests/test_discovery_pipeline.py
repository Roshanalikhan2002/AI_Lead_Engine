"""Lead discovery pipeline, filters, duplicates, and job lifecycle (offline)."""

from __future__ import annotations

import uuid

import pytest

from app.core.config import Settings, get_settings
from app.models.generation_job import GenerationJob
from app.models.lead import Lead
from app.services.google_places import GooglePlacesError, GooglePlacesService
from app.services.lead_discovery import run_generation_job
from app.services.lead_normalizer import passes_filters, to_lead
from app.services.offline_places_fixture import OFFLINE_PLACES
from app.services.place_types import PlaceBusiness
from app.utils.normalize import normalize_domain, normalize_phone


def _map_fixture_businesses() -> list[PlaceBusiness]:
    settings = Settings(GOOGLE_PLACES_API_KEY="x", GOOGLE_PLACES_MOCK="false", places_request_delay_seconds=0)
    service = GooglePlacesService(settings)

    class OneShot:
        def __init__(self):
            self.n = 0

        def post(self, url, headers=None, json=None):
            self.n += 1

            class R:
                status_code = 200
                text = ""

                def json(self_inner):
                    return {"places": OFFLINE_PLACES}

            return R()

        def close(self):
            pass

    with GooglePlacesService(settings, client=OneShot()) as svc:
        return svc.search_businesses(
            industry="Dental Clinics",
            keywords="dentist",
            city="Houston",
            state="Texas",
            country="USA",
            min_rating=None,
            quantity=10,
        )


def test_normalize_phone_and_domain():
    assert normalize_phone("+1 (713) 555-0101") == "17135550101"
    assert normalize_domain("https://www.Example.com/path") == "example.com"
    assert normalize_domain(None) is None
    assert normalize_domain("") is None


@pytest.mark.parametrize(
    "website_filter,expect_pass",
    [
        ("any", True),
        ("yes", True),
        ("no", False),
    ],
)
def test_website_filter_has_website(website_filter, expect_pass):
    business = PlaceBusiness(
        google_place_id="p1",
        company_name="Clinic",
        rating=4.5,
        review_count=40,
        website="https://clinic.com",
    )
    assert (
        passes_filters(business, min_rating=4.0, min_reviews=20, website_filter=website_filter) is expect_pass
    )


@pytest.mark.parametrize(
    "website_filter,expect_pass",
    [
        ("any", True),
        ("yes", False),
        ("no", True),
    ],
)
def test_website_filter_no_website(website_filter, expect_pass):
    business = PlaceBusiness(
        google_place_id="p2",
        company_name="Clinic",
        rating=4.5,
        review_count=40,
        website=None,
    )
    assert (
        passes_filters(business, min_rating=4.0, min_reviews=20, website_filter=website_filter) is expect_pass
    )


def test_min_rating_and_reviews_filters():
    business = PlaceBusiness(
        google_place_id="p3",
        company_name="Clinic",
        rating=3.9,
        review_count=19,
        website="https://x.com",
    )
    assert not passes_filters(business, min_rating=4.0, min_reviews=None, website_filter="any")
    assert not passes_filters(business, min_rating=None, min_reviews=20, website_filter="any")

    ok = PlaceBusiness(
        google_place_id="p4",
        company_name="Clinic",
        rating=4.0,
        review_count=20,
        website="https://x.com",
    )
    assert passes_filters(ok, min_rating=4.0, min_reviews=20, website_filter="any")


def test_missing_rating_fails_min_rating_filter():
    business = PlaceBusiness(google_place_id="p5", company_name="No Rating", rating=None, review_count=100)
    assert not passes_filters(business, min_rating=4.0, min_reviews=None, website_filter="any")


def test_to_lead_normalization_and_missing_fields():
    business = PlaceBusiness(
        google_place_id="ChIJmockDental003",
        company_name="Neighborhood Family Dentistry",
        phone="(713) 555-0103",
        website=None,
        rating=4.2,
        review_count=45,
        city="Houston",
        state="Texas",
        country="United States",
    )
    lead = to_lead(
        business,
        industry="Dental Clinics",
        organization_id=uuid.uuid4(),
        source="google_places_mock",
    )
    assert lead.website is None
    assert lead.normalized_domain is None
    assert lead.normalized_phone == "7135550103"
    assert lead.source == "google_places_mock"


def test_pipeline_save_and_dedupe_second_run(SessionLocal, monkeypatch, mock_places_settings, zero_places_delay):
    monkeypatch.setattr("app.services.lead_discovery.SessionLocal", SessionLocal)
    monkeypatch.setattr("app.services.lead_discovery.get_settings", lambda: mock_places_settings)

    db = SessionLocal()
    job1 = GenerationJob(
        status="pending",
        country="USA",
        state="Texas",
        city="Houston",
        industry="Dental Clinics",
        keywords="dentist",
        min_rating=None,
        min_reviews=None,
        website_filter="any",
        requested_quantity=10,
    )
    db.add(job1)
    db.commit()
    job1_id = job1.id
    db.close()

    run_generation_job(job1_id)

    db = SessionLocal()
    job = db.get(GenerationJob, job1_id)
    assert job is not None
    assert job.status == "completed"
    assert job.found_quantity == 10
    first_count = db.query(Lead).count()
    assert first_count >= 1
    assert first_count == job.saved_quantity
    sources = {row.source for row in db.query(Lead).all()}
    assert sources == {"google_places_mock"}
    assert all(lead.generation_job_id == job1_id for lead in db.query(Lead).all())
    db.close()

    db = SessionLocal()
    job2 = GenerationJob(
        status="pending",
        country="USA",
        state="Texas",
        city="Houston",
        industry="Dental Clinics",
        keywords="dentist",
        min_rating=None,
        min_reviews=None,
        website_filter="any",
        requested_quantity=10,
    )
    db.add(job2)
    db.commit()
    job2_id = job2.id
    db.close()

    run_generation_job(job2_id)

    db = SessionLocal()
    job2 = db.get(GenerationJob, job2_id)
    assert job2.status == "completed"
    assert job2.duplicates_skipped >= first_count
    assert db.query(Lead).count() == first_count
    place_ids = [row.google_place_id for row in db.query(Lead).all()]
    assert len(place_ids) == len(set(place_ids))
    db.close()


def test_pipeline_applies_filters(SessionLocal, monkeypatch, mock_places_settings, zero_places_delay):
    monkeypatch.setattr("app.services.lead_discovery.SessionLocal", SessionLocal)
    monkeypatch.setattr("app.services.lead_discovery.get_settings", lambda: mock_places_settings)

    db = SessionLocal()
    job = GenerationJob(
        status="pending",
        country="USA",
        state="Texas",
        city="Houston",
        industry="Dental Clinics",
        keywords="dentist",
        min_rating=4.0,
        min_reviews=20,
        website_filter="yes",
        requested_quantity=10,
    )
    db.add(job)
    db.commit()
    job_id = job.id
    db.close()

    run_generation_job(job_id)

    db = SessionLocal()
    leads = db.query(Lead).all()
    assert leads
    for lead in leads:
        assert lead.rating is not None and lead.rating >= 4.0
        assert lead.review_count is not None and lead.review_count >= 20
        assert lead.website
    job = db.get(GenerationJob, job_id)
    assert job.status == "completed"
    assert job.progress if hasattr(job, "progress") else True
    db.close()


def test_job_failure_sets_error_message(SessionLocal, monkeypatch):
    monkeypatch.setattr("app.services.lead_discovery.SessionLocal", SessionLocal)

    class BoomPlaces:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def search_businesses(self, **kwargs):
            raise GooglePlacesError("Google Places authentication failed. Check GOOGLE_PLACES_API_KEY and API permissions.", 403)

    monkeypatch.setattr("app.services.lead_discovery.GooglePlacesService", lambda _settings: BoomPlaces())
    monkeypatch.setattr(
        "app.services.lead_discovery.get_settings",
        lambda: Settings(GOOGLE_PLACES_API_KEY="x", GOOGLE_PLACES_MOCK="false"),
    )

    db = SessionLocal()
    job = GenerationJob(
        status="pending",
        country="USA",
        state="Texas",
        city="Houston",
        industry="Dental Clinics",
        keywords="dentist",
        website_filter="any",
        requested_quantity=5,
    )
    db.add(job)
    db.commit()
    job_id = job.id
    db.close()

    run_generation_job(job_id)

    db = SessionLocal()
    job = db.get(GenerationJob, job_id)
    assert job.status == "failed"
    assert job.error_message
    assert "authentication" in job.error_message.lower()
    assert "traceback" not in job.error_message.lower()
    db.close()


def test_duplicate_google_place_id_constraint(db_session):
    first = Lead(
        id=uuid.uuid4(),
        company_name="One",
        google_place_id="dup-1",
        source="google_places_mock",
    )
    second = Lead(
        id=uuid.uuid4(),
        company_name="Two",
        google_place_id="dup-1",
        source="google_places_mock",
    )
    db_session.add(first)
    db_session.commit()
    db_session.add(second)
    with pytest.raises(Exception):
        db_session.commit()
