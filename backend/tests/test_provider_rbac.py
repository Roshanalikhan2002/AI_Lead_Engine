"""Phase 14 — provider test RBAC."""

from __future__ import annotations

from app.core.tenant import hash_password
from app.models.auth import OrganizationMember, User
from app.services.auth.service import issue_session


def _member_token(db_session, org_id, role: str, email: str) -> str:
    user = User(
        email=email,
        password_hash=hash_password("Password123!"),
        first_name="T",
        last_name="U",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(
        OrganizationMember(
            organization_id=org_id,
            user_id=user.id,
            role=role,
            status="active",
        )
    )
    db_session.commit()
    access, _ = issue_session(db_session, user=user, organization_id=org_id)
    return access


def test_member_cannot_run_provider_test(client, db_session, auth_tenant):
    token = _member_token(
        db_session, auth_tenant["organization_id"], "member", "member-prov@test.local"
    )
    res = client.post(
        "/api/system/providers/ai/test",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


def test_viewer_cannot_validate_config(client, db_session, auth_tenant):
    token = _member_token(
        db_session, auth_tenant["organization_id"], "viewer", "viewer-prov@test.local"
    )
    res = client.get(
        "/api/system/config/validate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


def test_manager_cannot_run_provider_test(client, db_session, auth_tenant):
    token = _member_token(
        db_session, auth_tenant["organization_id"], "manager", "mgr-prov@test.local"
    )
    res = client.post(
        "/api/system/providers/calendar/test",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403
