"""Phase 14 — production config validation."""

from __future__ import annotations

import pytest

from app.core.config import ProductionConfigError, Settings, get_settings, validate_settings
from app.services.system.config_validate import validate_production_config
from app.services.system.readiness import production_readiness


def test_config_validate_endpoint(client):
    res = client.get("/api/system/config/validate")
    assert res.status_code == 200
    body = res.json()
    assert "items" in body
    assert "ok" in body
    assert "secret" not in str(body).lower() or "SECRET_KEY" in str(body)


def test_readiness_endpoint(client):
    res = client.get("/api/system/readiness")
    assert res.status_code == 200
    body = res.json()
    assert "checklist" in body
    ids = {c["id"] for c in body["checklist"]}
    assert "authentication" in ids
    assert "backups" in ids
    # Backups are documented-only warning
    backups = next(c for c in body["checklist"] if c["id"] == "backups")
    assert backups["status"] == "WARNING"


def test_production_rejects_mock_billing(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "a-strong-production-secret-key-32chars")
    monkeypatch.setenv("BILLING_PROVIDER", "mock")
    monkeypatch.setenv("GOOGLE_PLACES_MOCK", "false")
    get_settings.cache_clear()
    with pytest.raises(ProductionConfigError):
        validate_settings(Settings())


def test_structured_validation_pass_warning_error(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("SECRET_KEY", "dev-secret-key-for-local-tests-32")
    get_settings.cache_clear()
    result = validate_production_config(Settings())
    assert result["error_count"] == 0
    severities = {i["severity"] for i in result["items"]}
    assert severities <= {"pass", "warning", "error"}


def test_readiness_never_pass_live_without_test(db_session, auth_tenant, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_API_KEY", "sk-x")
    get_settings.cache_clear()
    ready = production_readiness(db=db_session, organization_id=auth_tenant["organization_id"])
    ai = next(c for c in ready["checklist"] if c["id"] == "ai")
    assert ai["status"] in {"WARNING", "BLOCKED"}
    assert "LIVE-TESTED" not in ai["detail"]
