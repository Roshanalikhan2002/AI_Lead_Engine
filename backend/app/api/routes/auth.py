"""Auth, organization, and team API routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.tenant import (
    ROLE_PERMISSIONS,
    TenantContext,
    TenantDep,
    get_tenant_context,
    normalize_email,
    require_permission,
)
from app.models.auth import Organization, OrganizationInvitation, OrganizationMember, User
from app.services.auth import service as auth_service
from app.services.auth.service import AuthError
from app.services.system.audit import write_audit
from app.services.system.rate_limit import enforce_rate_limit

router = APIRouter(tags=["Auth"])


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)
    first_name: str = ""
    last_name: str = ""
    organization_name: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str
    organization_id: uuid.UUID | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class OrgCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    timezone: str = "UTC"
    default_currency: str = "USD"


class OrgSettingsPatch(BaseModel):
    name: str | None = None
    timezone: str | None = None
    default_currency: str | None = None
    logo_url: str | None = None


class SwitchOrgRequest(BaseModel):
    refresh_token: str | None = None


class InviteRequest(BaseModel):
    email: str
    role: str = "member"


class AcceptInviteRequest(BaseModel):
    token: str
    password: str | None = None
    first_name: str = ""
    last_name: str = ""


class MemberRolePatch(BaseModel):
    role: str


class MemberStatusPatch(BaseModel):
    status: str


def _token_response(access: str, refresh: str, user: User, org: Organization, role: str) -> dict:
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "user": auth_service.user_public(user),
        "organization": auth_service.org_public(org),
        "role": role,
        "permissions": sorted(ROLE_PERMISSIONS.get(role, set())),
    }


def _raise_auth(exc: AuthError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        detail={"error": {"code": exc.code.upper(), "message": str(exc)}},
    ) from exc


@router.post("/api/auth/register", summary="Register user and create organization")
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    enforce_rate_limit(request, sensitive=True)
    try:
        user, org, access, refresh = auth_service.register_user(
            db,
            email=payload.email,
            password=payload.password,
            first_name=payload.first_name,
            last_name=payload.last_name,
            organization_name=payload.organization_name,
        )
    except AuthError as exc:
        _raise_auth(exc)
    return _token_response(access, refresh, user, org, "owner")


@router.post("/api/auth/login", summary="Login")
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    # Per-IP login rate limit
    from app.services.system.rate_limit import SlidingWindowLimiter, client_key

    # reuse module limiter via enforce with sensitive
    enforce_rate_limit(request, sensitive=True)
    try:
        user, org, member, access, refresh = auth_service.login_user(
            db,
            email=payload.email,
            password=payload.password,
            organization_id=payload.organization_id,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except AuthError as exc:
        _raise_auth(exc)
    return _token_response(access, refresh, user, org, member.role)


@router.post("/api/auth/refresh", summary="Refresh access token")
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> dict:
    try:
        access, refresh_tok, ctx = auth_service.refresh_session(db, payload.refresh_token)
    except AuthError as exc:
        _raise_auth(exc)
    user = db.get(User, ctx.user_id)
    org = db.get(Organization, ctx.organization_id)
    assert user and org
    return _token_response(access, refresh_tok, user, org, ctx.role)


@router.post("/api/auth/logout", summary="Logout / revoke refresh session")
def logout(payload: LogoutRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    tenant = getattr(request.state, "tenant", None)
    auth_service.logout_session(
        db, payload.refresh_token, tenant if isinstance(tenant, TenantContext) else None
    )
    return {"status": "ok"}


@router.get("/api/auth/me", summary="Current user and active organization")
def me(tenant: TenantDep, db: Session = Depends(get_db)) -> dict:
    user = db.get(User, tenant.user_id)
    org = db.get(Organization, tenant.organization_id)
    assert user and org
    return {
        "user": auth_service.user_public(user),
        "organization": auth_service.org_public(org),
        "role": tenant.role,
        "permissions": sorted(tenant.permissions),
    }


@router.post("/api/auth/forgot-password", summary="Request password reset")
def forgot_password(payload: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    enforce_rate_limit(request, sensitive=True)
    raw = auth_service.request_password_reset(db, payload.email)
    settings = get_settings()
    resp: dict = {
        "status": "ok",
        "message": "If that email is registered, a reset link will be available.",
        "email_sent": False,
    }
    # Never claim email was sent when provider isn't configured
    if raw and settings.email_send_enabled and not settings.email_test_mode:
        resp["email_sent"] = False  # delivery not wired for auth emails yet
        resp["message"] = "If that email is registered, password reset instructions were prepared."
    elif raw and (settings.app_env or "").lower() in {"development", "test"}:
        # Dev-only: return token so tests/local QA work without email
        resp["reset_token"] = raw
        resp["message"] = "Reset token created (development only — email delivery not configured)."
    return resp


@router.post("/api/auth/reset-password", summary="Reset password with token")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> dict:
    try:
        auth_service.reset_password(db, payload.token, payload.new_password)
    except AuthError as exc:
        _raise_auth(exc)
    return {"status": "ok"}


@router.post("/api/auth/change-password", summary="Change password while authenticated")
def change_password(
    payload: ChangePasswordRequest, tenant: TenantDep, db: Session = Depends(get_db)
) -> dict:
    try:
        auth_service.change_password(db, tenant.user_id, payload.current_password, payload.new_password)
    except AuthError as exc:
        _raise_auth(exc)
    return {"status": "ok"}


@router.get("/api/organizations", summary="List organizations for current user")
def list_organizations(tenant: TenantDep, db: Session = Depends(get_db)) -> list[dict]:
    rows = (
        db.query(Organization, OrganizationMember)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .filter(
            OrganizationMember.user_id == tenant.user_id,
            OrganizationMember.status == "active",
        )
        .all()
    )
    return [
        {**auth_service.org_public(org), "role": member.role, "active": org.id == tenant.organization_id}
        for org, member in rows
    ]


@router.get("/api/organizations/{organization_id}", summary="Get organization if member")
def get_organization(
    organization_id: uuid.UUID, tenant: TenantDep, db: Session = Depends(get_db)
) -> dict:
    member = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.user_id == tenant.user_id,
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.status == "active",
        )
        .one_or_none()
    )
    if not member:
        raise HTTPException(status_code=404, detail="Organization not found")
    org = db.get(Organization, organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return {**auth_service.org_public(org), "role": member.role}


@router.post("/api/organizations", summary="Create organization")
def create_organization(
    payload: OrgCreateRequest, tenant: TenantDep, db: Session = Depends(get_db)
) -> dict:
    user = db.get(User, tenant.user_id)
    assert user
    org = auth_service.create_organization(
        db,
        name=payload.name,
        owner=user,
        timezone_name=payload.timezone,
        currency=payload.default_currency,
    )
    db.commit()
    db.refresh(org)
    return auth_service.org_public(org)


@router.post("/api/organizations/{organization_id}/switch", summary="Switch active organization")
def switch_organization(
    organization_id: uuid.UUID,
    payload: SwitchOrgRequest,
    tenant: TenantDep,
    db: Session = Depends(get_db),
) -> dict:
    try:
        access, refresh = auth_service.switch_organization(
            db, tenant, organization_id, refresh_token=payload.refresh_token
        )
    except Exception as exc:  # noqa: BLE001
        if isinstance(exc, HTTPException):
            raise
        from fastapi import HTTPException as H

        raise H(status_code=403, detail="Cannot switch to that organization") from exc
    user = db.get(User, tenant.user_id)
    org = db.get(Organization, organization_id)
    member = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.user_id == tenant.user_id,
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.status == "active",
        )
        .one()
    )
    assert user and org
    return _token_response(access, refresh, user, org, member.role)


@router.get("/api/organization/settings", summary="Organization settings")
def get_org_settings(
    tenant: TenantContext = Depends(require_permission("settings.view")),
    db: Session = Depends(get_db),
) -> dict:
    org = db.get(Organization, tenant.organization_id)
    assert org
    return {
        **auth_service.org_public(org),
        "branding": org.branding_json or {},
    }


@router.patch("/api/organization/settings", summary="Update organization settings")
def patch_org_settings(
    payload: OrgSettingsPatch,
    tenant: TenantContext = Depends(require_permission("settings.manage")),
    db: Session = Depends(get_db),
) -> dict:
    org = db.get(Organization, tenant.organization_id)
    assert org
    if payload.name is not None:
        org.name = payload.name.strip()[:255]
    if payload.timezone is not None:
        org.timezone = payload.timezone.strip()[:64] or "UTC"
    if payload.default_currency is not None:
        org.default_currency = payload.default_currency.strip().upper()[:8] or "USD"
    if payload.logo_url is not None:
        org.logo_url = payload.logo_url.strip()[:512] or None
    db.commit()
    db.refresh(org)
    return auth_service.org_public(org)


@router.get("/api/team", summary="List team members")
def list_team(
    tenant: TenantContext = Depends(require_permission("team.view")),
    db: Session = Depends(get_db),
) -> list[dict]:
    rows = (
        db.query(OrganizationMember, User)
        .join(User, User.id == OrganizationMember.user_id)
        .filter(
            OrganizationMember.organization_id == tenant.organization_id,
            OrganizationMember.status != "removed",
        )
        .all()
    )
    return [
        {
            "id": str(m.id),
            "user_id": str(u.id),
            "email": u.email,
            "first_name": u.first_name,
            "last_name": u.last_name,
            "role": m.role,
            "status": m.status,
            "joined_at": m.joined_at.isoformat() if m.joined_at else None,
        }
        for m, u in rows
    ]


@router.post("/api/team/invite", summary="Invite team member")
def invite_member(
    payload: InviteRequest,
    tenant: TenantContext = Depends(require_permission("team.manage")),
    db: Session = Depends(get_db),
) -> dict:
    try:
        inv, raw = auth_service.create_invitation(
            db,
            organization_id=tenant.organization_id,
            email=payload.email,
            role=payload.role,
            invited_by=tenant.user_id,
        )
    except AuthError as exc:
        _raise_auth(exc)
    settings = get_settings()
    email_configured = bool(settings.email_send_enabled and not settings.email_test_mode)
    resp = {
        "id": str(inv.id),
        "email": inv.email,
        "role": inv.role,
        "expires_at": inv.expires_at.isoformat(),
        "email_sent": False,
        "message": (
            "Invitation created — email delivery is not configured."
            if not email_configured
            else "Invitation created."
        ),
    }
    if (settings.app_env or "").lower() in {"development", "test"}:
        resp["invite_token"] = raw  # tests/local only
    return resp


@router.post("/api/auth/invitations/accept", summary="Accept organization invitation")
def accept_invitation(payload: AcceptInviteRequest, db: Session = Depends(get_db)) -> dict:
    try:
        user, org, access, refresh = auth_service.accept_invitation(
            db,
            token=payload.token,
            password=payload.password,
            first_name=payload.first_name,
            last_name=payload.last_name,
        )
    except AuthError as exc:
        _raise_auth(exc)
    member = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.user_id == user.id,
            OrganizationMember.organization_id == org.id,
            OrganizationMember.status == "active",
        )
        .one()
    )
    return _token_response(access, refresh, user, org, member.role)


@router.get("/api/auth/invitations/{token}", summary="Peek invitation (public)")
def peek_invitation(token: str, db: Session = Depends(get_db)) -> dict:
    from app.core.tenant import hash_token

    inv = (
        db.query(OrganizationInvitation)
        .filter(
            OrganizationInvitation.token_hash == hash_token(token),
            OrganizationInvitation.accepted_at.is_(None),
            OrganizationInvitation.revoked_at.is_(None),
        )
        .one_or_none()
    )
    if not inv:
        raise HTTPException(status_code=404, detail="Invitation not found")
    org = db.get(Organization, inv.organization_id)
    return {
        "email": inv.email,
        "role": inv.role,
        "organization_name": org.name if org else None,
        "expires_at": inv.expires_at.isoformat(),
    }


@router.patch("/api/team/{member_id}/role", summary="Change member role")
def change_role(
    member_id: uuid.UUID,
    payload: MemberRolePatch,
    tenant: TenantContext = Depends(require_permission("team.manage")),
    db: Session = Depends(get_db),
) -> dict:
    if payload.role not in {"owner", "admin", "manager", "member", "viewer"}:
        raise HTTPException(status_code=400, detail="Invalid role")
    if payload.role == "owner" and tenant.role != "owner":
        raise HTTPException(status_code=403, detail="Only an owner can assign the owner role")

    member = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.id == member_id,
            OrganizationMember.organization_id == tenant.organization_id,
        )
        .one_or_none()
    )
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    if member.role == "owner" and payload.role != "owner":
        if auth_service.count_owners(db, tenant.organization_id) <= 1:
            raise HTTPException(status_code=400, detail="Cannot demote the last owner")

    old = member.role
    member.role = payload.role
    write_audit(
        db,
        action="role_changed",
        entity_type="organization_member",
        entity_id=str(member.id),
        actor_type="user",
        actor_id=str(tenant.user_id),
        metadata={"from": old, "to": payload.role},
        organization_id=tenant.organization_id,
        actor_user_id=tenant.user_id,
    )
    db.commit()
    return {"id": str(member.id), "role": member.role}


@router.patch("/api/team/{member_id}/status", summary="Change member status")
def change_status(
    member_id: uuid.UUID,
    payload: MemberStatusPatch,
    tenant: TenantContext = Depends(require_permission("team.manage")),
    db: Session = Depends(get_db),
) -> dict:
    if payload.status not in {"active", "suspended"}:
        raise HTTPException(status_code=400, detail="Invalid status")
    member = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.id == member_id,
            OrganizationMember.organization_id == tenant.organization_id,
        )
        .one_or_none()
    )
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    if member.role == "owner" and payload.status != "active":
        if auth_service.count_owners(db, tenant.organization_id) <= 1:
            raise HTTPException(status_code=400, detail="Cannot suspend the last owner")
    member.status = payload.status
    db.commit()
    return {"id": str(member.id), "status": member.status}


@router.delete("/api/team/{member_id}", summary="Remove member")
def remove_member(
    member_id: uuid.UUID,
    tenant: TenantContext = Depends(require_permission("team.manage")),
    db: Session = Depends(get_db),
) -> dict:
    member = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.id == member_id,
            OrganizationMember.organization_id == tenant.organization_id,
        )
        .one_or_none()
    )
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    if member.role == "owner":
        if auth_service.count_owners(db, tenant.organization_id) <= 1:
            raise HTTPException(status_code=400, detail="Cannot remove the last owner")
        if tenant.role != "owner":
            raise HTTPException(status_code=403, detail="Only an owner can remove another owner")
    member.status = "removed"
    write_audit(
        db,
        action="member_removed",
        entity_type="organization_member",
        entity_id=str(member.id),
        actor_type="user",
        actor_id=str(tenant.user_id),
        organization_id=tenant.organization_id,
        actor_user_id=tenant.user_id,
    )
    db.commit()
    return {"status": "ok"}
