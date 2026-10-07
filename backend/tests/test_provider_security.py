"""Phase 14 — provider security (no secret leakage)."""

from __future__ import annotations

from app.core.config import get_settings
from app.services.system.providers import provider_statuses, system_health


def test_provider_payloads_never_include_secrets(monkeypatch, db_session):
    monkeypatch.setenv("AI_API_KEY", "sk-secret-value-do-not-leak")
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "places-secret-xyz")
    monkeypatch.setenv("EMAIL_VERIFICATION_API_KEY", "verify-secret-xyz")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_live_should_not_appear")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_should_not_appear")
    monkeypatch.setenv("EMAIL_WEBHOOK_SECRET", "email_wh_secret")
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("BILLING_PROVIDER", "stripe")
    get_settings.cache_clear()

    for payload in (provider_statuses(), system_health(db=db_session)):
        blob = str(payload)
        assert "sk-secret-value" not in blob
        assert "places-secret" not in blob
        assert "verify-secret" not in blob
        assert "sk_live_should_not" not in blob
        assert "whsec_should_not" not in blob
        assert "email_wh_secret" not in blob


def test_provider_test_response_has_no_secrets(client, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setenv("AI_API_KEY", "sk-should-not-leak")
    get_settings.cache_clear()
    res = client.post("/api/system/providers/ai/test")
    assert "sk-should-not-leak" not in res.text
