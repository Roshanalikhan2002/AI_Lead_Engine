"""Phase 12 — cross-tenant isolation tests."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import create_app
from app.models.campaign import Campaign
from app.models.lead import Lead
from app.models.meeting import Meeting
from app.models.meeting_type import MeetingType
from app.services.auth.service import register_user


def _authed_client(SessionLocal, monkeypatch, access_token: str) -> TestClient:
    monkeypatch.setattr("app.core.database.SessionLocal", SessionLocal)
    monkeypatch.setattr("app.services.lead_discovery.SessionLocal", SessionLocal)
    app = create_app()

    def _override_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_db
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {access_token}"})
    client._app_ref = app  # type: ignore[attr-defined]
    return client


def test_cross_tenant_lead_isolation(db_session, SessionLocal, monkeypatch, auth_tenant):
    # Org A already from auth_tenant
    lead_a = Lead(
        id=uuid.uuid4(),
        organization_id=auth_tenant["organization_id"],
        company_name="Org A Lead",
        source="mock",
    )
    db_session.add(lead_a)

    user_b, org_b, access_b, _ = register_user(
        db_session,
        email="orgb@example.com",
        password="Password123!",
        first_name="B",
        last_name="User",
        organization_name="Org B",
    )
    lead_b = Lead(
        id=uuid.uuid4(),
        organization_id=org_b.id,
        company_name="Org B Lead",
        source="mock",
    )
    campaign_b = Campaign(
        id=uuid.uuid4(),
        organization_id=org_b.id,
        name="B Campaign",
        status="draft",
        timezone="UTC",
        daily_send_limit=50,
        hourly_send_limit=10,
        send_start_hour=9,
        send_end_hour=17,
        send_on_weekends=False,
    )
    mt_b = MeetingType(
        id=uuid.uuid4(),
        organization_id=org_b.id,
        name="B Call",
        duration_minutes=30,
        buffer_before_minutes=0,
        buffer_after_minutes=0,
        active=True,
    )
    db_session.add_all([lead_b, campaign_b, mt_b])
    db_session.commit()

    # Authenticate as Org A
    client_a = _authed_client(SessionLocal, monkeypatch, auth_tenant["access_token"])
    assert client_a.get(f"/api/leads/{lead_b.id}").status_code == 404
    assert client_a.get(f"/api/leads/{lead_a.id}").status_code == 200
    listed = client_a.get("/api/leads").json()
    ids = [row["id"] for row in listed.get("items", listed if isinstance(listed, list) else [])]
    # LeadListResponse uses items
    if "items" in listed:
        ids = [i["id"] for i in listed["items"]]
    assert str(lead_b.id) not in ids
    assert str(lead_a.id) in ids

    assert client_a.get(f"/api/campaigns/{campaign_b.id}").status_code == 404

    # Org B cannot see A
    client_b = _authed_client(SessionLocal, monkeypatch, access_b)
    assert client_b.get(f"/api/leads/{lead_a.id}").status_code == 404
    assert client_b.get(f"/api/leads/{lead_b.id}").status_code == 200

    client_a._app_ref.dependency_overrides.clear()  # type: ignore[attr-defined]
    client_b._app_ref.dependency_overrides.clear()  # type: ignore[attr-defined]


def test_analytics_tenant_scoped(db_session, SessionLocal, monkeypatch, auth_tenant, client):
    for i in range(3):
        db_session.add(
            Lead(
                id=uuid.uuid4(),
                organization_id=auth_tenant["organization_id"],
                company_name=f"A{i}",
                source="mock",
            )
        )
    user_b, org_b, access_b, _ = register_user(
        db_session,
        email="analytics-b@example.com",
        password="Password123!",
        first_name="B",
        last_name="User",
        organization_name="Analytics B",
    )
    for i in range(2):
        db_session.add(
            Lead(
                id=uuid.uuid4(),
                organization_id=org_b.id,
                company_name=f"B{i}",
                source="mock",
            )
        )
    db_session.commit()

    a_list = client.get("/api/leads?limit=100").json()
    assert a_list["total"] == 3

    client_b = _authed_client(SessionLocal, monkeypatch, access_b)
    b_list = client_b.get("/api/leads?limit=100").json()
    assert b_list["total"] == 2
    client_b._app_ref.dependency_overrides.clear()  # type: ignore[attr-defined]
