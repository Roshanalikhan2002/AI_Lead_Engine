"""Shared pytest fixtures — isolated DB + authenticated default tenant."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.core.database import Base, get_db
from app.core.org_flush import set_fallback_organization_id
from app.core.tenant import set_current_tenant
from app.main import create_app
from app.services.auth.service import issue_session, register_user
import app.core.org_flush  # noqa: F401


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _disable_rate_limits_by_default(monkeypatch):
    """Avoid flaky 429s across the suite; dedicated tests re-enable limits."""
    monkeypatch.setenv("API_RATE_LIMIT_ENABLED", "false")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-jwt-signing-32chars")
    monkeypatch.setenv("APP_ENV", "test")
    get_settings.cache_clear()


@pytest.fixture()
def db_engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def SessionLocal(db_engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=db_engine)


@pytest.fixture()
def db_session(SessionLocal):
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def auth_tenant(db_session):
    """Default org/user for Phase 12 — used by API client and flush fallback."""
    user, org, access, refresh = register_user(
        db_session,
        email="owner@test.leadflow.local",
        password="Password123!",
        first_name="Test",
        last_name="Owner",
        organization_name="Test Agency",
    )
    token = set_fallback_organization_id(org.id)
    try:
        yield {
            "user": user,
            "org": org,
            "access_token": access,
            "refresh_token": refresh,
            "organization_id": org.id,
            "user_id": user.id,
        }
    finally:
        from app.core.org_flush import reset_fallback_organization_id

        reset_fallback_organization_id(token)


@pytest.fixture()
def client(db_session, SessionLocal, monkeypatch, auth_tenant):
    """API client wired to isolated DB; authenticated as default org owner."""
    monkeypatch.setattr("app.services.lead_discovery.SessionLocal", SessionLocal)
    monkeypatch.setattr("app.core.database.SessionLocal", SessionLocal)

    app = create_app()

    def _override_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_db
    with TestClient(app) as test_client:
        test_client.headers.update({"Authorization": f"Bearer {auth_tenant['access_token']}"})
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def mock_places_settings(monkeypatch):
    """Enable offline Places fixture without a real API key."""
    monkeypatch.setenv("GOOGLE_PLACES_MOCK", "true")
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "")
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.google_places_mock is True
    return settings


@pytest.fixture()
def zero_places_delay(monkeypatch):
    monkeypatch.setattr("app.services.google_places.time.sleep", lambda _s: None)
