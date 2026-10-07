"""Phase 14 — provider health tenant isolation."""

from __future__ import annotations

from app.core.config import get_settings
from app.core.tenant import hash_password
from app.models.auth import User
from app.models.provider_health import ProviderHealthState
from app.services.auth.service import create_organization, issue_session


def test_provider_health_is_org_scoped(client, db_session, auth_tenant, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "mock")
    get_settings.cache_clear()

    # Org A runs test
    res_a = client.post("/api/system/providers/ai/test")
    assert res_a.status_code == 200

    owner_b = User(
        email="owner-b-prov@test.local",
        password_hash=hash_password("Password123!"),
        first_name="B",
        last_name="Owner",
        is_active=True,
        is_verified=True,
    )
    db_session.add(owner_b)
    db_session.flush()
    org_b = create_organization(db_session, name="Provider Org B", owner=owner_b)
    db_session.commit()
    access_b, _ = issue_session(db_session, user=owner_b, organization_id=org_b.id)

    # Org B providers should not inherit Org A live_tested/success falsely as shared secret
    res_b = client.get("/api/system/providers", headers={"Authorization": f"Bearer {access_b}"})
    assert res_b.status_code == 200

    db_session.expire_all()
    a_rows = (
        db_session.query(ProviderHealthState)
        .filter(ProviderHealthState.organization_id == auth_tenant["organization_id"])
        .count()
    )
    b_rows = (
        db_session.query(ProviderHealthState)
        .filter(ProviderHealthState.organization_id == org_b.id)
        .count()
    )
    assert a_rows >= 1
    assert b_rows == 0
