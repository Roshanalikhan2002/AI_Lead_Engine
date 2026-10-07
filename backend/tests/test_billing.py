"""Phase 13 — billing plans, checkout, cancel/resume, permissions."""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from app.core.config import get_settings
from app.core.tenant import hash_password
from app.models.auth import OrganizationMember, User
from app.services.billing.service import ensure_free_subscription


def test_free_plan_works_without_provider(client, db_session, auth_tenant):
    ensure_free_subscription(db_session, auth_tenant["organization_id"])
    res = client.get("/api/billing/subscription")
    assert res.status_code == 200
    body = res.json()
    assert body["plan"] == "free"
    assert body["status"] == "active"
    assert body["billing_provider_configured"] is False


def test_list_plans(client):
    res = client.get("/api/billing/plans")
    assert res.status_code == 200
    plans = {p["id"] for p in res.json()["plans"]}
    assert plans == {"free", "starter", "growth", "agency", "enterprise"}
    enterprise = next(p for p in res.json()["plans"] if p["id"] == "enterprise")
    assert enterprise["contact_sales"] is True
    assert enterprise["monthly_price"] is None


def test_usage_endpoint(client, auth_tenant):
    res = client.get("/api/billing/usage")
    assert res.status_code == 200
    body = res.json()
    assert body["plan"] == "free"
    assert any(i["resource"] == "ai_qualifications" for i in body["items"])


def test_checkout_unconfigured(client, monkeypatch):
    monkeypatch.setenv("BILLING_PROVIDER", "unconfigured")
    get_settings.cache_clear()
    res = client.post(
        "/api/billing/checkout",
        json={"target_plan": "starter", "billing_interval": "month"},
    )
    assert res.status_code == 503
    body = res.json()
    assert body.get("error", {}).get("code") == "BILLING_NOT_CONFIGURED" or "not configured" in str(
        body
    ).lower()


def test_checkout_mock(client, monkeypatch):
    monkeypatch.setenv("BILLING_PROVIDER", "mock")
    monkeypatch.setenv("APP_ENV", "development")
    get_settings.cache_clear()
    res = client.post(
        "/api/billing/checkout",
        json={"target_plan": "starter", "billing_interval": "month"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["mode"] == "mock"
    assert body["checkout_url"].startswith("mock://")


def test_change_plan_mock(client, monkeypatch):
    monkeypatch.setenv("BILLING_PROVIDER", "mock")
    monkeypatch.setenv("APP_ENV", "development")
    get_settings.cache_clear()
    res = client.post(
        "/api/billing/change-plan",
        json={"target_plan": "growth", "billing_interval": "month"},
    )
    assert res.status_code == 200
    assert res.json()["plan"] == "growth"
    assert res.json()["status"] == "active"


def test_cancel_and_resume_mock(client, monkeypatch):
    monkeypatch.setenv("BILLING_PROVIDER", "mock")
    monkeypatch.setenv("APP_ENV", "development")
    get_settings.cache_clear()
    client.post("/api/billing/change-plan", json={"target_plan": "starter", "billing_interval": "month"})
    cancel = client.post("/api/billing/cancel", json={"cancel_at_period_end": True})
    assert cancel.status_code == 200
    assert cancel.json()["cancel_at_period_end"] is True
    resume = client.post("/api/billing/resume")
    assert resume.status_code == 200
    assert resume.json()["cancel_at_period_end"] is False


def test_member_cannot_change_plan(client, db_session, auth_tenant, monkeypatch):
    monkeypatch.setenv("BILLING_PROVIDER", "mock")
    get_settings.cache_clear()
    member = User(
        email="member-billing@test.local",
        password_hash=hash_password("Password123!"),
        first_name="Mem",
        last_name="Ber",
        is_active=True,
        is_verified=True,
    )
    db_session.add(member)
    db_session.flush()
    db_session.add(
        OrganizationMember(
            organization_id=auth_tenant["organization_id"],
            user_id=member.id,
            role="member",
            status="active",
        )
    )
    db_session.commit()
    from app.services.auth.service import issue_session

    access, _ = issue_session(db_session, user=member, organization_id=auth_tenant["organization_id"])
    res = client.post(
        "/api/billing/change-plan",
        json={"target_plan": "starter"},
        headers={"Authorization": f"Bearer {access}"},
    )
    assert res.status_code == 403


def test_viewer_cannot_manage_billing(client, db_session, auth_tenant):
    viewer = User(
        email="viewer-billing@test.local",
        password_hash=hash_password("Password123!"),
        first_name="View",
        last_name="Er",
        is_active=True,
        is_verified=True,
    )
    db_session.add(viewer)
    db_session.flush()
    db_session.add(
        OrganizationMember(
            organization_id=auth_tenant["organization_id"],
            user_id=viewer.id,
            role="viewer",
            status="active",
        )
    )
    db_session.commit()
    from app.services.auth.service import issue_session

    access, _ = issue_session(db_session, user=viewer, organization_id=auth_tenant["organization_id"])
    res = client.get("/api/billing/usage", headers={"Authorization": f"Bearer {access}"})
    assert res.status_code == 403


def test_cannot_patch_organization_plan(client, auth_tenant):
    res = client.patch(
        f"/api/organizations/{auth_tenant['organization_id']}",
        json={"plan": "enterprise"},
    )
    assert res.status_code in {404, 405, 422}


def test_portal_unconfigured(client):
    res = client.post("/api/billing/portal")
    assert res.status_code == 503
