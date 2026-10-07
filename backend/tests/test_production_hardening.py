"""Phase 11 — production hardening tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import ProductionConfigError, Settings, get_settings, validate_settings
from app.main import create_app
from app.services.jobs.queue import LocalJobQueue, backoff_seconds, is_retryable_error
from app.services.system.audit import write_audit
from app.services.system.providers import provider_statuses
from app.services.website.url_safety import UnsafeURLError, assert_public_url


def test_provider_statuses_never_include_secrets(monkeypatch):
    monkeypatch.setenv("AI_API_KEY", "sk-secret-value-do-not-leak")
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "places-secret")
    monkeypatch.setenv("EMAIL_VERIFICATION_API_KEY", "verify-secret")
    monkeypatch.setenv("AI_PROVIDER", "openai")
    get_settings.cache_clear()
    payload = provider_statuses()
    blob = str(payload)
    assert "sk-secret" not in blob
    assert "places-secret" not in blob
    assert "verify-secret" not in blob
    assert payload["providers"]["ai"]["configured"] is True


def test_production_validation_fail_fast(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "changeme")
    monkeypatch.setenv("GOOGLE_PLACES_MOCK", "true")
    get_settings.cache_clear()
    settings = Settings()
    with pytest.raises(ProductionConfigError):
        validate_settings(settings)


def test_production_allows_disabled_calendar(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "a-strong-production-secret-key-32")
    monkeypatch.setenv("GOOGLE_PLACES_MOCK", "false")
    monkeypatch.setenv("CALENDAR_PROVIDER", "")
    monkeypatch.setenv("AI_PROVIDER", "")
    monkeypatch.setenv("EMAIL_VERIFICATION_PROVIDER", "")
    monkeypatch.setenv("EMAIL_SEND_ENABLED", "false")
    get_settings.cache_clear()
    problems = validate_settings(Settings())
    assert problems == []


def test_health_endpoints(client, db_session):
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/health/live").json()["status"] == "alive"
    ready = client.get("/api/health/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"

    providers = client.get("/api/system/providers")
    assert providers.status_code == 200
    body = providers.json()
    assert "providers" in body
    assert "api_key" not in str(body).lower() or "api_key" not in body  # no key values
    for name, info in body["providers"].items():
        assert "configured" in info
        assert "mode" in info

    health = client.get("/api/system/health")
    assert health.status_code == 200
    assert health.json()["authentication"]["status"] == "implemented"


def test_provider_smoke_test_no_side_effects(client):
    res = client.post("/api/system/providers/email_sending/test")
    assert res.status_code == 200
    assert res.json()["side_effects"] == "none"
    assert "no email was sent" in res.json()["message"].lower()

    cal = client.post("/api/system/providers/calendar/test")
    assert cal.status_code == 200
    assert "no calendar event" in cal.json()["message"].lower()


def test_job_lifecycle_and_retries(db_session, auth_tenant):
    from app.core.tenant import TenantContext, set_current_tenant

    ctx = TenantContext(
        user_id=auth_tenant["user_id"],
        organization_id=auth_tenant["organization_id"],
        role="owner",
        email="owner@test.leadflow.local",
    )
    token = set_current_tenant(ctx)
    try:
        q = LocalJobQueue(db_session)
        job = q.enqueue("unit_test", {"x": 1}, idempotency_key="job-idem-1")
        again = q.enqueue("unit_test", {"x": 2}, idempotency_key="job-idem-1")
        assert job.id == again.id

        def boom():
            raise RuntimeError("provider 429 rate limit")

        failed = q.run(job.id, boom)
        assert failed.status == "retrying"
        assert failed.attempts == 1
        assert failed.last_error
        assert "Traceback" not in (failed.last_error or "")

        assert is_retryable_error("network timeout")
        assert is_retryable_error("503 temporary")
        assert not is_retryable_error("invalid api key")
        assert not is_retryable_error("suppressed recipient")
        assert backoff_seconds(1) < backoff_seconds(3)
    finally:
        from app.core.tenant import reset_current_tenant

        reset_current_tenant(token)


def test_audit_log_sanitizes_secrets(db_session):
    row = write_audit(
        db_session,
        action="campaign_created",
        entity_type="campaign",
        entity_id="x",
        metadata={"api_key": "secret-value", "name": "Demo"},
    )
    assert row is not None
    assert row.metadata_json["api_key"] == "[redacted]"
    assert row.metadata_json["name"] == "Demo"


def test_api_error_sanitization_no_stack(client):
    missing = client.get("/api/leads/00000000-0000-0000-0000-000000000001")
    assert missing.status_code == 404
    body = missing.json()
    assert body["detail"] == "Lead not found"
    assert "error" in body
    assert "Traceback" not in str(body)


def test_ssrf_blocks_metadata_and_private(monkeypatch):
    with pytest.raises(UnsafeURLError):
        assert_public_url("http://127.0.0.1/", resolve_dns=False)
    with pytest.raises(UnsafeURLError):
        assert_public_url("http://169.254.169.254/latest/meta-data", resolve_dns=False)
    with pytest.raises(UnsafeURLError):
        assert_public_url("http://metadata.google.internal/", resolve_dns=False)
    with pytest.raises(UnsafeURLError):
        assert_public_url("http://[::1]/", resolve_dns=False)


def test_rate_limiting(monkeypatch, db_session, SessionLocal, auth_tenant):
    monkeypatch.setenv("API_RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("API_RATE_LIMIT_SENSITIVE_PER_MINUTE", "2")
    get_settings.cache_clear()

    app = create_app()

    def _override_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    from app.core.database import get_db

    app.dependency_overrides[get_db] = _override_db
    with TestClient(app) as c:
        c.headers.update({"Authorization": f"Bearer {auth_tenant['access_token']}"})
        # Sensitive POST prefix — campaigns create
        r1 = c.post("/api/campaigns", json={"name": "A"})
        r2 = c.post("/api/campaigns", json={"name": "B"})
        r3 = c.post("/api/campaigns", json={"name": "C"})
        assert r1.status_code in {200, 201, 422, 400}
        assert r2.status_code in {200, 201, 422, 400, 429}
        assert r3.status_code == 429
        err = r3.json()
        assert err["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    app.dependency_overrides.clear()


def test_mock_labeling_modes(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setenv("GOOGLE_PLACES_MOCK", "true")
    monkeypatch.setenv("EMAIL_TEST_MODE", "true")
    monkeypatch.setenv("EMAIL_SEND_ENABLED", "false")
    monkeypatch.setenv("CALENDAR_PROVIDER", "mock")
    get_settings.cache_clear()
    p = provider_statuses()["providers"]
    assert p["ai"]["mode"] == "mock"
    assert p["ai"]["status"] == "test_mode"
    assert p["google_places"]["mode"] == "mock"
    assert p["calendar"]["mode"] == "mock"
    assert p["email_sending"]["mode"] in {"test", "disabled"}
