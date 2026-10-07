"""
External provider integration tests — SKIP unless credentials are present.

Run explicitly when configured:
  pytest tests/integration/providers -m integration

Never invent LIVE from key presence alone; each test asserts a real response.
"""

from __future__ import annotations

import os

import pytest

from app.core.config import get_settings


pytestmark = pytest.mark.integration


def _has(name: str) -> bool:
    return bool((os.environ.get(name) or "").strip())


@pytest.fixture(autouse=True)
def _clear_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_google_places_live_probe(db_session):
    if not _has("GOOGLE_PLACES_API_KEY") or os.environ.get("GOOGLE_PLACES_MOCK", "").lower() in {
        "1",
        "true",
        "yes",
    }:
        pytest.skip("GOOGLE_PLACES_API_KEY not configured for live probe")
    from app.services.system.provider_tests import run_provider_test

    result = run_provider_test(db_session, "google_places", organization_id=None)
    assert result["ok"] is True
    assert result["live_operation"] is True
    assert result["mode"] == "live"


def test_ai_live_probe(db_session):
    if not _has("AI_API_KEY") or (os.environ.get("AI_PROVIDER") or "").lower() in {
        "",
        "none",
        "mock",
        "unconfigured",
    }:
        pytest.skip("AI provider credentials not configured for live probe")
    from app.services.system.provider_tests import run_provider_test

    result = run_provider_test(db_session, "ai", organization_id=None)
    assert result["ok"] is True
    assert result["live_operation"] is True
    assert result["mode"] == "live"


def test_email_verification_live_probe(db_session):
    provider = (os.environ.get("EMAIL_VERIFICATION_PROVIDER") or "").lower()
    if provider in {"", "none", "mock", "unconfigured"} or not _has("PROVIDER_TEST_EMAIL"):
        pytest.skip("Email verification credentials / PROVIDER_TEST_EMAIL not configured")
    from app.services.system.provider_tests import run_provider_test

    result = run_provider_test(db_session, "email_verification", organization_id=None)
    assert result["ok"] is True
    assert result["live_operation"] is True
    assert result["mode"] == "live"


def test_email_sending_live_probe(db_session):
    if (
        os.environ.get("EMAIL_SEND_ENABLED", "").lower() not in {"1", "true", "yes"}
        or os.environ.get("EMAIL_TEST_MODE", "true").lower() in {"1", "true", "yes"}
        or not _has("PROVIDER_TEST_EMAIL")
        or not _has("SENDER_EMAIL")
    ):
        pytest.skip("Live email send flags / PROVIDER_TEST_EMAIL not configured")
    from app.services.system.provider_tests import run_provider_test

    result = run_provider_test(db_session, "email_sending", organization_id=None)
    assert result["ok"] is True
    assert result["live_operation"] is True
    assert result["mode"] == "live"
    assert result.get("side_effects") == "one_test_email"


def test_stripe_test_mode_probe(db_session):
    key = (os.environ.get("STRIPE_SECRET_KEY") or "").strip()
    if (os.environ.get("BILLING_PROVIDER") or "").lower() != "stripe" or not key.startswith("sk_test_"):
        pytest.skip("Stripe TEST credentials not configured")
    from app.services.system.provider_tests import run_provider_test

    result = run_provider_test(db_session, "billing", organization_id=None)
    assert result["ok"] is True
    assert result["mode"] == "test"
    assert result["live_operation"] is False  # Stripe sandbox is never LIVE
