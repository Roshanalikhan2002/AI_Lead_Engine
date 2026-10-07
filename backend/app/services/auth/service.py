"""Authentication and organization membership services."""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.tenant import (
    TenantContext,
    build_tenant_from_user_org,
    create_access_token,
    generate_token,
    hash_password,
    hash_token,
    normalize_email,
    verify_password,
)
from app.models.auth import (
    AuthSession,
    Organization,
    OrganizationInvitation,
    OrganizationMember,
    OrganizationUsage,
    PasswordResetToken,
    User,
)
from app.services.system.audit import write_audit

logger = logging.getLogger(__name__)

SLUG_RE = re.compile(r"[^a-z0-9]+")


class AuthError(Exception):
    def __init__(self, message: str, *, code: str = "auth_error", status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def slugify(name: str) -> str:
    base = SLUG_RE.sub("-", (name or "").strip().lower()).strip("-") or "org"
    return base[:80]


def unique_slug(db: Session, name: str) -> str:
    base = slugify(name)
    candidate = base
    n = 1
    while db.query(Organization).filter(Organization.slug == candidate).one_or_none():
        n += 1
        candidate = f"{base}-{n}"
    return candidate


def ensure_usage(db: Session, organization_id: uuid.UUID) -> OrganizationUsage:
    row = (
        db.query(OrganizationUsage)
        .filter(OrganizationUsage.organization_id == organization_id)
        .one_or_none()
    )
    if row:
        return row
    row = OrganizationUsage(organization_id=organization_id)
    db.add(row)
    db.flush()
    return row


_LEGACY_USAGE_FIELDS = {
    "leads_discovered",
    "website_analyses",
    "emails_discovered",
    "emails_verified",
    "ai_qualifications",
    "ai_generations",
    "emails_sent",
    "meetings_booked",
}


def bump_usage(db: Session, organization_id: uuid.UUID, field: str, amount: int = 1) -> None:
    if field not in _LEGACY_USAGE_FIELDS:
        return
    row = ensure_usage(db, organization_id)
    current = int(getattr(row, field, 0) or 0)
    setattr(row, field, current + amount)
    db.add(row)


def create_organization(
    db: Session,
    *,
    name: str,
    owner: User,
    timezone_name: str = "UTC",
    currency: str = "USD",
) -> Organization:
    org = Organization(
        name=name.strip(),
        slug=unique_slug(db, name),
        timezone=timezone_name or "UTC",
        default_currency=(currency or "USD").upper()[:8],
        status="active",
        plan="free",
    )
    db.add(org)
    db.flush()
    member = OrganizationMember(
        organization_id=org.id,
        user_id=owner.id,
        role="owner",
        status="active",
        joined_at=datetime.now(timezone.utc),
    )
    db.add(member)
    ensure_usage(db, org.id)
    from app.services.billing.service import ensure_free_subscription

    ensure_free_subscription(db, org.id)
    write_audit(
        db,
        action="organization_created",
        entity_type="organization",
        entity_id=str(org.id),
        actor_type="user",
        actor_id=str(owner.id),
        metadata={"name": org.name},
        organization_id=org.id,
        actor_user_id=owner.id,
        commit=False,
    )
    return org


def register_user(
    db: Session,
    *,
    email: str,
    password: str,
    first_name: str,
    last_name: str,
    organization_name: str | None = None,
) -> tuple[User, Organization, str, str]:
    """Returns user, org, access_token, refresh_token."""
    email_n = normalize_email(email)
    if not email_n or "@" not in email_n:
        raise AuthError("Valid email is required", code="invalid_email")
    if len(password or "") < 8:
        raise AuthError("Password must be at least 8 characters", code="weak_password")

    existing = db.query(User).filter(User.email == email_n).one_or_none()
    if existing:
        raise AuthError(
            "An account with this email already exists. Sign in instead.",
            code="email_exists",
            status_code=409,
        )

    user = User(
        email=email_n,
        password_hash=hash_password(password),
        first_name=(first_name or "").strip()[:100],
        last_name=(last_name or "").strip()[:100],
        is_active=True,
        is_verified=False,
    )
    db.add(user)
    db.flush()

    org_name = (organization_name or f"{user.first_name or 'My'} Agency").strip()
    org = create_organization(db, name=org_name, owner=user)
    db.commit()
    db.refresh(user)
    db.refresh(org)

    access, refresh = issue_session(db, user=user, organization_id=org.id)
    return user, org, access, refresh


def issue_session(
    db: Session,
    *,
    user: User,
    organization_id: uuid.UUID,
    ip: str | None = None,
    user_agent: str | None = None,
) -> tuple[str, str]:
    member = build_tenant_from_user_org(db, user, organization_id)
    settings = get_settings()
    raw_refresh = generate_token(48)
    session = AuthSession(
        user_id=user.id,
        organization_id=organization_id,
        refresh_token_hash=hash_token(raw_refresh),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_ttl_days),
        ip_address=(ip or "")[:64] or None,
        user_agent=(user_agent or "")[:255] or None,
    )
    db.add(session)
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)

    access = create_access_token(
        user_id=user.id,
        organization_id=organization_id,
        role=member.role,
        session_id=session.id,
    )
    return access, raw_refresh


def login_user(
    db: Session,
    *,
    email: str,
    password: str,
    ip: str | None = None,
    user_agent: str | None = None,
    organization_id: uuid.UUID | None = None,
) -> tuple[User, Organization, OrganizationMember, str, str]:
    email_n = normalize_email(email)
    user = db.query(User).filter(User.email == email_n).one_or_none()
    # Constant messaging — do not reveal whether email exists
    if not user or not verify_password(password, user.password_hash):
        write_audit(
            db,
            action="login_failed",
            actor_type="user",
            actor_id=email_n,
            metadata={"reason": "invalid_credentials"},
            organization_id=None,
            commit=True,
        )
        raise AuthError("Invalid email or password", code="invalid_credentials", status_code=401)
    if not user.is_active:
        raise AuthError("Account is inactive", code="user_inactive", status_code=403)

    memberships = (
        db.query(OrganizationMember)
        .filter(OrganizationMember.user_id == user.id, OrganizationMember.status == "active")
        .all()
    )
    if not memberships:
        raise AuthError("No organization membership", code="no_membership", status_code=403)

    if organization_id:
        member = next((m for m in memberships if m.organization_id == organization_id), None)
        if not member:
            raise AuthError("Not a member of that organization", code="not_a_member", status_code=403)
    else:
        member = memberships[0]

    org = db.get(Organization, member.organization_id)
    if not org or org.status != "active":
        raise AuthError("Organization is not active", code="org_inactive", status_code=403)

    access, refresh = issue_session(
        db, user=user, organization_id=org.id, ip=ip, user_agent=user_agent
    )
    write_audit(
        db,
        action="login",
        entity_type="user",
        entity_id=str(user.id),
        actor_type="user",
        actor_id=str(user.id),
        organization_id=org.id,
        actor_user_id=user.id,
        commit=True,
    )
    return user, org, member, access, refresh


def refresh_session(db: Session, refresh_token: str) -> tuple[str, str, TenantContext]:
    token_h = hash_token(refresh_token)
    session = (
        db.query(AuthSession)
        .filter(AuthSession.refresh_token_hash == token_h, AuthSession.revoked_at.is_(None))
        .one_or_none()
    )
    if not session:
        raise AuthError("Invalid refresh token", code="invalid_refresh", status_code=401)
    if session.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        session.revoked_at = datetime.now(timezone.utc)
        db.commit()
        raise AuthError("Refresh token expired", code="refresh_expired", status_code=401)

    user = db.get(User, session.user_id)
    if not user or not user.is_active:
        raise AuthError("Account is inactive", code="user_inactive", status_code=403)

    # Rotate refresh token
    session.revoked_at = datetime.now(timezone.utc)
    access, new_refresh = issue_session(db, user=user, organization_id=session.organization_id)
    ctx = build_tenant_from_user_org(db, user, session.organization_id)
    return access, new_refresh, ctx


def logout_session(db: Session, refresh_token: str | None, tenant: TenantContext | None) -> None:
    if refresh_token:
        token_h = hash_token(refresh_token)
        session = (
            db.query(AuthSession)
            .filter(AuthSession.refresh_token_hash == token_h)
            .one_or_none()
        )
        if session and session.revoked_at is None:
            session.revoked_at = datetime.now(timezone.utc)
            db.commit()
    if tenant:
        write_audit(
            db,
            action="logout",
            entity_type="user",
            entity_id=str(tenant.user_id),
            actor_type="user",
            actor_id=str(tenant.user_id),
            organization_id=tenant.organization_id,
            actor_user_id=tenant.user_id,
            commit=True,
        )


def switch_organization(
    db: Session, tenant: TenantContext, organization_id: uuid.UUID, refresh_token: str | None = None
) -> tuple[str, str]:
    user = db.get(User, tenant.user_id)
    if not user:
        raise AuthError("Unauthorized", code="unauthorized", status_code=401)
    build_tenant_from_user_org(db, user, organization_id)

    if refresh_token:
        token_h = hash_token(refresh_token)
        session = (
            db.query(AuthSession)
            .filter(AuthSession.refresh_token_hash == token_h, AuthSession.revoked_at.is_(None))
            .one_or_none()
        )
        if session and session.user_id == user.id:
            session.revoked_at = datetime.now(timezone.utc)
            db.commit()

    return issue_session(db, user=user, organization_id=organization_id)


def request_password_reset(db: Session, email: str) -> str | None:
    """Always returns None to caller message; raw token only if user exists (for email/dev)."""
    email_n = normalize_email(email)
    user = db.query(User).filter(User.email == email_n).one_or_none()
    if not user:
        return None
    settings = get_settings()
    raw = generate_token(32)
    row = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_token(raw),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.password_reset_ttl_minutes),
    )
    db.add(row)
    db.commit()
    return raw


def reset_password(db: Session, token: str, new_password: str) -> None:
    if len(new_password or "") < 8:
        raise AuthError("Password must be at least 8 characters", code="weak_password")
    token_h = hash_token(token)
    row = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token_hash == token_h, PasswordResetToken.used_at.is_(None))
        .one_or_none()
    )
    if not row:
        raise AuthError("Invalid or expired reset token", code="invalid_reset_token", status_code=400)
    exp = row.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < datetime.now(timezone.utc):
        raise AuthError("Invalid or expired reset token", code="invalid_reset_token", status_code=400)

    user = db.get(User, row.user_id)
    if not user:
        raise AuthError("Invalid or expired reset token", code="invalid_reset_token", status_code=400)
    user.password_hash = hash_password(new_password)
    row.used_at = datetime.now(timezone.utc)
    # Revoke all sessions
    db.query(AuthSession).filter(
        AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)
    ).update({"revoked_at": datetime.now(timezone.utc)})
    db.commit()


def change_password(db: Session, user_id: uuid.UUID, current: str, new_password: str) -> None:
    user = db.get(User, user_id)
    if not user or not verify_password(current, user.password_hash):
        raise AuthError("Current password is incorrect", code="invalid_password", status_code=400)
    if len(new_password or "") < 8:
        raise AuthError("Password must be at least 8 characters", code="weak_password")
    user.password_hash = hash_password(new_password)
    db.commit()


def create_invitation(
    db: Session,
    *,
    organization_id: uuid.UUID,
    email: str,
    role: str,
    invited_by: uuid.UUID,
) -> tuple[OrganizationInvitation, str]:
    if role not in {"admin", "manager", "member", "viewer"}:
        raise AuthError("Invalid invitation role", code="invalid_role")
    try:
        from app.services.billing.usage import get_limit
        from app.models.auth import OrganizationInvitation

        limit = get_limit(db, organization_id, "team_members")
        if limit is not None:
            active = (
                db.query(OrganizationMember)
                .filter(
                    OrganizationMember.organization_id == organization_id,
                    OrganizationMember.status == "active",
                )
                .count()
            )
            pending = (
                db.query(OrganizationInvitation)
                .filter(
                    OrganizationInvitation.organization_id == organization_id,
                    OrganizationInvitation.accepted_at.is_(None),
                    OrganizationInvitation.revoked_at.is_(None),
                )
                .count()
            )
            if active + pending + 1 > limit:
                raise AuthError(
                    "Team member limit reached for your plan.",
                    code="TEAM_MEMBER_LIMIT_REACHED",
                    status_code=402,
                )
    except AuthError:
        raise
    email_n = normalize_email(email)
    existing_user = db.query(User).filter(User.email == email_n).one_or_none()
    if existing_user:
        member = (
            db.query(OrganizationMember)
            .filter(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == existing_user.id,
                OrganizationMember.status == "active",
            )
            .one_or_none()
        )
        if member:
            raise AuthError("User is already a member", code="already_member")

    settings = get_settings()
    raw = generate_token(32)
    inv = OrganizationInvitation(
        organization_id=organization_id,
        email=email_n,
        role=role,
        token_hash=hash_token(raw),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.invitation_ttl_days),
        invited_by=invited_by,
    )
    db.add(inv)
    write_audit(
        db,
        action="member_invited",
        entity_type="organization_invitation",
        entity_id=str(inv.id) if inv.id else None,
        actor_type="user",
        actor_id=str(invited_by),
        metadata={"email": email_n, "role": role},
        organization_id=organization_id,
        actor_user_id=invited_by,
        commit=False,
    )
    db.commit()
    db.refresh(inv)
    return inv, raw


def accept_invitation(
    db: Session,
    *,
    token: str,
    password: str | None = None,
    first_name: str = "",
    last_name: str = "",
) -> tuple[User, Organization, str, str]:
    token_h = hash_token(token)
    inv = (
        db.query(OrganizationInvitation)
        .filter(
            OrganizationInvitation.token_hash == token_h,
            OrganizationInvitation.accepted_at.is_(None),
            OrganizationInvitation.revoked_at.is_(None),
        )
        .one_or_none()
    )
    if not inv:
        raise AuthError("Invalid or expired invitation", code="invalid_invitation", status_code=400)
    exp = inv.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < datetime.now(timezone.utc):
        raise AuthError("Invalid or expired invitation", code="invalid_invitation", status_code=400)

    user = db.query(User).filter(User.email == inv.email).one_or_none()
    if not user:
        if not password or len(password) < 8:
            raise AuthError("Password required to create account", code="password_required")
        user = User(
            email=inv.email,
            password_hash=hash_password(password),
            first_name=(first_name or "").strip()[:100],
            last_name=(last_name or "").strip()[:100],
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        db.flush()
    elif not user.is_active:
        raise AuthError("Account is inactive", code="user_inactive", status_code=403)

    member = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == inv.organization_id,
            OrganizationMember.user_id == user.id,
        )
        .one_or_none()
    )
    if member:
        member.status = "active"
        member.role = inv.role
        member.joined_at = datetime.now(timezone.utc)
    else:
        member = OrganizationMember(
            organization_id=inv.organization_id,
            user_id=user.id,
            role=inv.role,
            status="active",
            joined_at=datetime.now(timezone.utc),
            invited_at=inv.created_at,
        )
        db.add(member)

    inv.accepted_at = datetime.now(timezone.utc)
    org = db.get(Organization, inv.organization_id)
    assert org is not None
    write_audit(
        db,
        action="member_joined",
        entity_type="organization_member",
        entity_id=str(user.id),
        actor_type="user",
        actor_id=str(user.id),
        metadata={"role": inv.role},
        organization_id=org.id,
        actor_user_id=user.id,
        commit=False,
    )
    db.commit()
    access, refresh = issue_session(db, user=user, organization_id=org.id)
    return user, org, access, refresh


def count_owners(db: Session, organization_id: uuid.UUID) -> int:
    return (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.role == "owner",
            OrganizationMember.status == "active",
        )
        .count()
    )


def user_public(user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }


def org_public(org: Organization) -> dict:
    return {
        "id": str(org.id),
        "name": org.name,
        "slug": org.slug,
        "logo_url": org.logo_url,
        "timezone": org.timezone,
        "default_currency": org.default_currency,
        "status": org.status,
        "plan": org.plan,
    }
