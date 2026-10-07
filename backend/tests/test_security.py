"""Security and configuration checks for Phase 1 (offline)."""

from __future__ import annotations

from pathlib import Path

from app.core.config import Settings
from app.services.offline_places_fixture import OFFLINE_PLACES


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"


def test_env_example_has_placeholders_only():
    example = (BACKEND / ".env.example").read_text(encoding="utf-8")
    assert "GOOGLE_PLACES_API_KEY=" in example
    assert "DATABASE_URL=" in example
    assert "FRONTEND_URL=" in example
    assert "GOOGLE_PLACES_MOCK=false" in example
    assert "AIza" not in example


def test_gitignore_covers_env_and_local_db():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in gitignore
    assert "backend/.env" in gitignore
    assert "*.db" in gitignore or "*.sqlite3" in gitignore


def test_no_hardcoded_google_api_keys_in_backend_source():
    skip_names = {".venv", "__pycache__"}
    offenders: list[str] = []
    for path in (BACKEND / "app").rglob("*.py"):
        if any(part in skip_names for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8")
        if "AIza" in text:
            offenders.append(str(path))
    assert offenders == []


def test_api_responses_never_include_api_key(
    client,
    monkeypatch,
    mock_places_settings,
    zero_places_delay,
):
    monkeypatch.setattr("app.services.lead_discovery.get_settings", lambda: mock_places_settings)

    created = client.post(
        "/api/generation",
        json={
            "country": "USA",
            "state": "Texas",
            "city": "Houston",
            "industry": "Dental Clinics",
            "keywords": "dentist",
            "min_rating": 4.0,
            "min_reviews": 20,
            "website_filter": "any",
            "quantity": 5,
        },
    )
    assert created.status_code == 202
    job_id = created.json()["job_id"]
    status_text = client.get(f"/api/generation/{job_id}").text
    leads_text = client.get("/api/leads").text
    assert "offline-mock-key" not in status_text
    assert "offline-mock-key" not in leads_text
    assert "GOOGLE_PLACES_API_KEY" not in status_text
    assert "traceback" not in status_text.lower()


def test_production_default_mock_flag_is_false():
    clean = Settings.model_construct(google_places_mock=False, google_places_api_key="")
    assert clean.google_places_mock is False


def test_fixture_businesses_cover_incomplete_fields():
    assert len(OFFLINE_PLACES) == 10
    assert any("websiteUri" not in p for p in OFFLINE_PLACES)
    assert any("nationalPhoneNumber" not in p for p in OFFLINE_PLACES)
    assert any("rating" not in p for p in OFFLINE_PLACES)
    assert any("userRatingCount" not in p for p in OFFLINE_PLACES)
