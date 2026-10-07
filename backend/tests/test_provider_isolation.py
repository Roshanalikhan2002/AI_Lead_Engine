"""Offline unit tests for provider-test isolation (Phase 15)."""

from __future__ import annotations

from app.services.billing.usage import get_usage_value, increment_usage
from app.services.system.e2e_pipeline import provider_status_matrix, run_isolated_e2e_pipeline
from app.services.system.test_org import (
    PROVIDER_TEST_LEAD_SOURCE,
    PROVIDER_TEST_ORG_SLUG,
    ensure_provider_test_organization,
    is_provider_test_org,
)
from app.models.lead import Lead


def test_ensure_provider_test_organization_idempotent(db_session):
    a = ensure_provider_test_organization(db_session)
    b = ensure_provider_test_organization(db_session)
    assert a.id == b.id
    assert a.slug == PROVIDER_TEST_ORG_SLUG
    assert is_provider_test_org(db_session, a.id)


def test_provider_test_org_usage_not_incremented(db_session):
    org = ensure_provider_test_organization(db_session)
    before = get_usage_value(db_session, org.id, "ai_qualifications")
    increment_usage(db_session, org.id, "ai_qualifications", amount=5, check=False)
    after = get_usage_value(db_session, org.id, "ai_qualifications")
    assert after == before


def test_provider_test_flag_skips_customer_usage(db_session, auth_tenant):
    org_id = auth_tenant["organization_id"]
    before = get_usage_value(db_session, org_id, "emails_sent")
    increment_usage(db_session, org_id, "emails_sent", amount=3, check=False, provider_test=True)
    after = get_usage_value(db_session, org_id, "emails_sent")
    assert after == before


def test_provider_matrix_never_invents_live(db_session, monkeypatch):
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "")
    monkeypatch.setenv("AI_PROVIDER", "")
    monkeypatch.setenv("EMAIL_VERIFICATION_PROVIDER", "")
    monkeypatch.setenv("BILLING_PROVIDER", "unconfigured")
    from app.core.config import get_settings

    get_settings.cache_clear()
    matrix = provider_status_matrix(db_session)
    for row in matrix["providers"]:
        assert row["mode"] != "live"
        assert row["live_tested"] is False
        assert row["result"] in {
            "NOT CONFIGURED",
            "MOCK",
            "DISABLED",
            "CONFIGURED",
            "TEST",
            "ERROR",
        }


def test_isolated_e2e_creates_provider_test_lead(db_session, auth_tenant, monkeypatch):
    monkeypatch.setenv("GOOGLE_PLACES_MOCK", "false")
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "")
    monkeypatch.setenv("AI_PROVIDER", "")
    monkeypatch.setenv("EMAIL_VERIFICATION_PROVIDER", "")
    monkeypatch.setenv("EMAIL_SEND_ENABLED", "false")
    monkeypatch.setenv("EMAIL_TEST_MODE", "true")
    monkeypatch.setenv("REPLY_INBOUND_ENABLED", "false")
    monkeypatch.setenv("CALENDAR_PROVIDER", "")
    monkeypatch.setenv("BILLING_PROVIDER", "unconfigured")
    from app.core.config import get_settings

    get_settings.cache_clear()

    class _FakeAnalysis:
        analysis_status = "completed"

    class _FakeDiscovery:
        status = "no_public_email"
        emails_found = 0

    monkeypatch.setattr(
        "app.services.website.analyzer.analyze_lead_website",
        lambda db, lead_id, **kwargs: _FakeAnalysis(),
    )
    monkeypatch.setattr(
        "app.services.contacts.discovery.discover_lead_contacts",
        lambda db, lead_id, **kwargs: _FakeDiscovery(),
    )

    result = run_isolated_e2e_pipeline(
        db_session,
        actor_user_id=auth_tenant["user_id"],
        send_email=False,
    )
    assert result["provider_test"] is True
    assert result["organization_slug"] == PROVIDER_TEST_ORG_SLUG
    lead = db_session.get(Lead, __import__("uuid").UUID(result["lead_id"]))
    assert lead is not None
    assert lead.source == PROVIDER_TEST_LEAD_SOURCE
    assert any(s["stage"] == "isolated_test_lead" and s.get("ok") for s in result["stages"])
    for s in result["stages"]:
        if s.get("live_operation"):
            assert s.get("ok") is True


def test_matrix_endpoint(client):
    res = client.get("/api/system/providers/matrix")
    assert res.status_code == 200
    body = res.json()
    assert "providers" in body
    assert "note" in body
    names = {p["provider"] for p in body["providers"]}
    assert "google_places" in names
    assert "billing" in names


def test_e2e_endpoint_admin(client, monkeypatch):
    monkeypatch.setenv("EMAIL_SEND_ENABLED", "false")
    monkeypatch.setenv("EMAIL_TEST_MODE", "true")
    from app.core.config import get_settings

    get_settings.cache_clear()

    class _FakeAnalysis:
        analysis_status = "completed"

    class _FakeDiscovery:
        status = "no_public_email"
        emails_found = 0

    monkeypatch.setattr(
        "app.services.website.analyzer.analyze_lead_website",
        lambda db, lead_id, **kwargs: _FakeAnalysis(),
    )
    monkeypatch.setattr(
        "app.services.contacts.discovery.discover_lead_contacts",
        lambda db, lead_id, **kwargs: _FakeDiscovery(),
    )

    res = client.post("/api/system/providers/e2e-test")
    assert res.status_code == 200
    body = res.json()
    assert body["provider_test"] is True
    assert body["organization_slug"] == PROVIDER_TEST_ORG_SLUG
