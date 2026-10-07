"""Phase 12 — authentication tests."""

from __future__ import annotations

import pytest

from app.core.tenant import hash_password, verify_password
from app.models.auth import User
from app.services.auth.service import AuthError, login_user, register_user, request_password_reset, reset_password


def test_password_hashing_not_plaintext():
    h = hash_password("Password123!")
    assert h != "Password123!"
    assert verify_password("Password123!", h)
    assert not verify_password("wrong", h)


def test_register_login_me(client, db_session):
    # Register a second user via API
    reg = client.post(
        "/api/auth/register",
        json={
            "email": "newuser@example.com",
            "password": "Password123!",
            "first_name": "New",
            "last_name": "User",
            "organization_name": "New Org",
        },
        headers={},  # override default auth — TestClient merges headers; clear by recreating
    )
    # client fixture always sends Authorization — register is public so OK
    assert reg.status_code == 200, reg.text
    body = reg.json()
    assert "access_token" in body
    assert "password_hash" not in str(body)
    assert body["role"] == "owner"

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "newuser@example.com"
    assert "permissions" in me.json()


def test_login_wrong_password(client):
    bad = client.post(
        "/api/auth/login",
        json={"email": "owner@test.leadflow.local", "password": "WrongPassword!"},
    )
    assert bad.status_code == 401
    assert "password_hash" not in bad.text.lower()


def test_password_reset_flow(db_session, auth_tenant):
    raw = request_password_reset(db_session, "owner@test.leadflow.local")
    assert raw
    reset_password(db_session, raw, "NewPassword123!")
    with pytest.raises(AuthError):
        reset_password(db_session, raw, "AnotherPassword123!")  # single-use
    user, org, member, access, refresh = login_user(
        db_session, email="owner@test.leadflow.local", password="NewPassword123!"
    )
    assert access


def test_unauthenticated_private_api(SessionLocal, monkeypatch, auth_tenant):
    from app.core.database import get_db
    from app.main import create_app
    from fastapi.testclient import TestClient

    monkeypatch.setattr("app.core.database.SessionLocal", SessionLocal)
    app = create_app()

    def _override_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_db
    with TestClient(app) as c:
        res = c.get("/api/leads")  # no auth header
        assert res.status_code == 401
    app.dependency_overrides.clear()
