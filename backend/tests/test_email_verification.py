"""Phase 4 email verification tests — mocked providers only, no live API calls."""

from __future__ import annotations

import uuid

import httpx
import pytest

from app.core.config import Settings
from app.models.lead import Lead
from app.models.lead_contact import LeadContact
from app.services.verification.providers import (
    HttpJsonVerificationProvider,
    MockVerificationProvider,
    UnconfiguredProvider,
    get_verification_provider,
    normalize_provider_payload,
)
from app.services.verification.service import verify_contact, verify_lead_contact
from app.services.verification.signals import is_free_email_provider, is_role_based_email


def test_unconfigured_provider_returns_unknown():
    result = UnconfiguredProvider().verify_email("sales@example.com")
    assert result.status == "unknown"
    assert result.is_valid is None


def test_mock_provider_patterns():
    mock = MockVerificationProvider()
    assert mock.verify_email("sales@brightsmile.example").status == "valid"
    assert mock.verify_email("invalid.user@x.com").status == "invalid"
    assert mock.verify_email("temp@mailinator.com").status == "risky"
    assert mock.verify_email("unknown.person@x.com").status == "unknown"
    assert mock.verify_email("error.case@x.com").status == "error"


def test_role_and_free_signals_do_not_invalidate():
    assert is_role_based_email("info@company.com") is True
    assert is_role_based_email("sales@company.com") is True
    assert is_role_based_email("john.smith@company.com") is False
    assert is_free_email_provider("owner@gmail.com") is True
    assert is_free_email_provider("sales@company.com") is False


def test_normalize_provider_payload():
    result = normalize_provider_payload(
        {"status": "deliverable", "disposable": False, "mx": True},
        provider_name="http",
    )
    assert result.status == "valid"
    assert result.mx_found is True

    risky = normalize_provider_payload(
        {"status": "valid", "is_disposable": True},
        provider_name="http",
    )
    assert risky.status == "risky"


def test_http_provider_timeout_and_rate_limit():
    class TimeoutClient:
        def post(self, *args, **kwargs):
            raise httpx.TimeoutException("timeout")

    provider = HttpJsonVerificationProvider(api_url="https://verify.example/check", api_key="k", client=TimeoutClient())
    assert provider.verify_email("a@b.com").status == "error"

    class RateClient:
        def post(self, *args, **kwargs):
            class R:
                status_code = 429
                text = "rate"

                def json(self):
                    return {}

            return R()

    provider2 = HttpJsonVerificationProvider(api_url="https://verify.example/check", api_key="k", client=RateClient())
    assert provider2.verify_email("a@b.com").summary == "Provider rate limited"


def test_verify_contact_unknown_without_provider(db_session, monkeypatch):
    monkeypatch.setenv("EMAIL_VERIFICATION_PROVIDER", "")
    monkeypatch.setenv("EMAIL_VERIFICATION_API_KEY", "")
    from app.core.config import get_settings

    get_settings.cache_clear()

    lead = Lead(id=uuid.uuid4(), company_name="Co", website="https://co.example", source="google_places_mock")
    contact = LeadContact(
        id=uuid.uuid4(),
        lead_id=lead.id,
        email="sales@co.example",
        normalized_email="sales@co.example",
        contact_type="sales",
        source="website_contact_page",
        source_url="https://co.example/contact",
        confidence="high",
        domain_match=True,
        is_primary=True,
    )
    db_session.add_all([lead, contact])
    db_session.commit()

    row = verify_contact(
        db_session,
        contact.id,
        provider=UnconfiguredProvider(),
        mx_checker=lambda _d: True,
    )
    assert row.status == "unknown"
    assert row.mx_found is True
    assert row.is_role_based is True
    # Discovery confidence untouched
    db_session.refresh(contact)
    assert contact.confidence == "high"


def test_verify_with_mock_provider(db_session):
    lead = Lead(id=uuid.uuid4(), company_name="Co", website="https://co.example", source="google_places_mock")
    good = LeadContact(
        id=uuid.uuid4(),
        lead_id=lead.id,
        email="sales@co.example",
        normalized_email="sales@co.example",
        contact_type="sales",
        source="website",
        confidence="high",
        domain_match=True,
        is_primary=True,
    )
    bad = LeadContact(
        id=uuid.uuid4(),
        lead_id=lead.id,
        email="invalid@co.example",
        normalized_email="invalid@co.example",
        contact_type="unknown",
        source="website",
        confidence="medium",
        domain_match=True,
        is_primary=False,
    )
    db_session.add_all([lead, good, bad])
    db_session.commit()

    mock = MockVerificationProvider()
    ok = verify_contact(db_session, good.id, provider=mock, mx_checker=lambda _d: True, force=True)
    assert ok.status == "valid"
    no = verify_contact(db_session, bad.id, provider=mock, mx_checker=lambda _d: False, force=True)
    assert no.status == "invalid"
    assert no.mx_found is False


def test_cache_skips_reverify_unless_forced(db_session):
    lead = Lead(id=uuid.uuid4(), company_name="Co", source="google_places_mock")
    contact = LeadContact(
        id=uuid.uuid4(),
        lead_id=lead.id,
        email="sales@co.example",
        normalized_email="sales@co.example",
        contact_type="sales",
        source="website",
        confidence="high",
        domain_match=True,
        is_primary=True,
    )
    db_session.add_all([lead, contact])
    db_session.commit()

    first = verify_contact(db_session, contact.id, provider=MockVerificationProvider(), mx_checker=lambda d: True)
    second = verify_contact(db_session, contact.id, provider=MockVerificationProvider(), mx_checker=lambda d: True)
    assert first.id == second.id
    forced = verify_lead_contact(
        db_session,
        lead.id,
        contact.id,
        force=True,
        provider=MockVerificationProvider(),
        mx_checker=lambda d: True,
    )
    assert forced.lead_contact_id == contact.id


def test_verification_api(client, SessionLocal, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("EMAIL_VERIFICATION_PROVIDER", "mock")
    get_settings.cache_clear()

    db = SessionLocal()
    lead = Lead(id=uuid.uuid4(), company_name="API Verify", website="https://co.example", source="google_places_mock")
    contact = LeadContact(
        id=uuid.uuid4(),
        lead_id=lead.id,
        email="sales@co.example",
        normalized_email="sales@co.example",
        contact_type="sales",
        source="website_contact_page",
        source_url="https://co.example/contact",
        confidence="high",
        domain_match=True,
        is_primary=True,
    )
    db.add_all([lead, contact])
    db.commit()
    lead_id, contact_id = lead.id, contact.id
    db.close()

    monkeypatch.setattr("app.services.verification.service.check_mx", lambda _d: True)
    monkeypatch.setattr("app.services.verification.service.SessionLocal", SessionLocal)

    verified = client.post(f"/api/leads/{lead_id}/contacts/{contact_id}/verify")
    assert verified.status_code == 200
    body = verified.json()
    assert body["verification"]["status"] == "valid"
    assert body["verification"]["provider"] == "mock"

    # Wrong lead should 404
    wrong = client.post(f"/api/leads/{uuid.uuid4()}/contacts/{contact_id}/verify")
    assert wrong.status_code == 404

    batch = client.post(
        "/api/leads/contacts/verify-batch",
        json={"contact_ids": [str(contact_id)], "only_unverified": False},
    )
    assert batch.status_code == 202
    job_id = batch.json()["job_id"]
    status = client.get(f"/api/leads/contact-verification-jobs/{job_id}")
    assert status.status_code == 200
    assert status.json()["status"] == "completed"

    detail = client.get(f"/api/leads/{lead_id}")
    assert detail.status_code == 200
    assert detail.json()["contacts"][0]["verification_status"] == "valid"
    # discovery confidence preserved separately
    assert detail.json()["contacts"][0]["confidence"] == "high"

    get_settings.cache_clear()


def test_get_provider_factory():
    none = get_verification_provider(Settings(EMAIL_VERIFICATION_PROVIDER=""))
    assert none.name == "none"
    mock = get_verification_provider(Settings(EMAIL_VERIFICATION_PROVIDER="mock"))
    assert mock.name == "mock"
    http = get_verification_provider(
        Settings(
            EMAIL_VERIFICATION_PROVIDER="http",
            EMAIL_VERIFICATION_API_KEY="k",
            EMAIL_VERIFICATION_API_URL="https://example.com/verify",
        )
    )
    assert http.name == "http"
