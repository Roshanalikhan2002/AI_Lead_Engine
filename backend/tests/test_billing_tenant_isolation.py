"""Phase 13 — billing tenant isolation."""

from __future__ import annotations

from app.core.config import get_settings
from app.core.tenant import hash_password
from app.models.auth import Organization, OrganizationMember, User
from app.models.billing import BillingCustomer, Subscription
from app.services.auth.service import create_organization, issue_session
from app.services.billing.service import ensure_free_subscription


def test_cross_tenant_billing_denied(client, db_session, auth_tenant, monkeypatch):
    monkeypatch.setenv("BILLING_PROVIDER", "mock")
    get_settings.cache_clear()

    # Org A (auth_tenant) upgrades
    client.post("/api/billing/change-plan", json={"target_plan": "starter"})

    # Org B with its own owner
    owner_b = User(
        email="owner-b-billing@test.local",
        password_hash=hash_password("Password123!"),
        first_name="Owner",
        last_name="B",
        is_active=True,
        is_verified=True,
    )
    db_session.add(owner_b)
    db_session.flush()
    org_b = create_organization(db_session, name="Agency B", owner=owner_b)
    db_session.commit()

    access_b, _ = issue_session(db_session, user=owner_b, organization_id=org_b.id)
    res = client.get("/api/billing/subscription", headers={"Authorization": f"Bearer {access_b}"})
    assert res.status_code == 200
    assert res.json()["plan"] == "free"
    assert res.json()["organization_id"] == str(org_b.id)

    # Org B cannot see Org A billing customer
    a_customers = (
        db_session.query(BillingCustomer)
        .filter(BillingCustomer.organization_id == auth_tenant["organization_id"])
        .count()
    )
    b_customers = (
        db_session.query(BillingCustomer)
        .filter(BillingCustomer.organization_id == org_b.id)
        .count()
    )
    assert a_customers >= 1
    assert b_customers == 0

    # Org B usage is independent
    usage_b = client.get("/api/billing/usage", headers={"Authorization": f"Bearer {access_b}"})
    assert usage_b.status_code == 200
    assert usage_b.json()["subscription"]["organization_id"] == str(org_b.id)
