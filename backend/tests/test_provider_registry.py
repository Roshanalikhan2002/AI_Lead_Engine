"""Phase 14 — provider registry modes (anti-hallucination)."""

from __future__ import annotations

from app.core.config import get_settings
from app.services.system.registry import PROVIDER_IDS, normalize_provider_id, provider_registry


def test_registry_contains_all_providers():
    payload = provider_registry()
    for pid in PROVIDER_IDS:
        assert pid in payload["providers"]
        info = payload["providers"][pid]
        assert "configured" in info
        assert "enabled" in info
        assert "mode" in info
        assert info["mode"] in {"unavailable", "mock", "test", "live", "disabled", "error"}


def test_key_presence_is_not_live(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.setenv("AI_API_KEY", "sk-test-not-real")
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "places-not-real")
    monkeypatch.setenv("GOOGLE_PLACES_MOCK", "false")
    get_settings.cache_clear()
    p = provider_registry()["providers"]
    assert p["ai"]["configured"] is True
    assert p["ai"]["mode"] != "live"
    assert p["ai"]["live_tested"] is False
    assert p["google_places"]["configured"] is True
    assert p["google_places"]["mode"] != "live"


def test_mock_never_labeled_live(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setenv("BILLING_PROVIDER", "mock")
    monkeypatch.setenv("CALENDAR_PROVIDER", "mock")
    get_settings.cache_clear()
    p = provider_registry()["providers"]
    assert p["ai"]["mode"] == "mock"
    assert p["billing"]["mode"] == "mock"
    assert p["calendar"]["mode"] == "mock"


def test_normalize_aliases():
    assert normalize_provider_id("places") == "google_places"
    assert normalize_provider_id("reply_inbound") == "email_inbound"
    assert normalize_provider_id("stripe") == "billing"
