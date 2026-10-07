"""Phase 14 — provider health tests (offline)."""

from __future__ import annotations

from app.core.config import get_settings
from app.models.provider_health import ProviderHealthState, ProviderOperationLog


def test_email_sending_test_sends_nothing_by_default(client):
    res = client.post("/api/system/providers/email_sending/test")
    assert res.status_code == 200
    body = res.json()
    assert body["side_effects"] == "none"
    assert "no email was sent" in body["message"].lower()
    assert body.get("live_operation") is False


def test_calendar_test_creates_no_event(client):
    res = client.post("/api/system/providers/calendar/test")
    assert res.status_code == 200
    assert "no calendar event" in res.json()["message"].lower()


def test_mock_ai_test(client, monkeypatch, db_session, auth_tenant):
    monkeypatch.setenv("AI_PROVIDER", "mock")
    get_settings.cache_clear()
    res = client.post("/api/system/providers/ai/test")
    assert res.status_code == 200
    assert res.json()["ok"] is True
    assert res.json()["mode"] == "mock"
    assert res.json()["live_operation"] is False

    db_session.expire_all()
    rows = (
        db_session.query(ProviderHealthState)
        .filter(
            ProviderHealthState.provider == "ai",
            ProviderHealthState.organization_id == auth_tenant["organization_id"],
        )
        .all()
    )
    assert len(rows) >= 1
    assert rows[0].live_tested is False

    logs = db_session.query(ProviderOperationLog).filter(ProviderOperationLog.provider == "ai").all()
    assert len(logs) >= 1


def test_billing_mock_test(client, monkeypatch):
    monkeypatch.setenv("BILLING_PROVIDER", "mock")
    monkeypatch.setenv("APP_ENV", "development")
    get_settings.cache_clear()
    res = client.post("/api/system/providers/billing/test")
    assert res.status_code == 200
    assert res.json()["mode"] == "mock"
    assert "not a real payment" in res.json()["message"].lower()


def test_verification_requires_test_email_for_live(client, monkeypatch):
    monkeypatch.setenv("EMAIL_VERIFICATION_PROVIDER", "http")
    monkeypatch.setenv("EMAIL_VERIFICATION_API_KEY", "x")
    monkeypatch.setenv("PROVIDER_TEST_EMAIL", "")
    get_settings.cache_clear()
    res = client.post("/api/system/providers/email_verification/test")
    assert res.status_code == 200
    assert res.json()["error_code"] == "TEST_RECIPIENT_NOT_CONFIGURED"


def test_providers_endpoint_has_health_fields(client):
    res = client.get("/api/system/providers")
    assert res.status_code == 200
    for name, info in res.json()["providers"].items():
        assert "configured" in info
        assert "mode" in info
        assert "healthy" in info
        assert "live_tested" in info
        blob = str(info)
        assert "sk-secret" not in blob
        assert "api_key" not in blob.lower() or "credentials_present" in blob.lower()
