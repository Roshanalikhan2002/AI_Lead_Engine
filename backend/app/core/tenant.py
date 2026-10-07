"""Tenant context, permissions, and auth dependencies."""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import uuid
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Annotated, Callable

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.models.auth import AuthSession, Organization, OrganizationMember, User

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)

_tenant_ctx: ContextVar["TenantContext | None"] = ContextVar("tenant_ctx", default=None)

# role -> permissions
ROLE_PERMISSIONS: dict[str, set[str]] = {
    "owner": {
        "leads.view",
        "leads.create",
        "leads.update",
        "leads.delete",
        "contacts.view",
        "contacts.update",
        "campaigns.view",
        "campaigns.create",
        "campaigns.update",
        "campaigns.delete",
        "campaigns.send",
        "replies.view",
        "replies.respond",
        "meetings.view",
        "meetings.manage",
        "pipeline.view",
        "pipeline.manage",
        "settings.view",
        "settings.manage",
        "team.view",
        "team.manage",
        "audit.view",
        "billing.view",
        "billing.manage",
        "org.manage",
        "integrations.manage",
    },
    "admin": {
        "leads.view",
        "leads.create",
        "leads.update",
        "leads.delete",
        "contacts.view",
        "contacts.update",
        "campaigns.view",
        "campaigns.create",
        "campaigns.update",
        "campaigns.delete",
        "campaigns.send",
        "replies.view",
        "replies.respond",
        "meetings.view",
        "meetings.manage",
        "pipeline.view",
        "pipeline.manage",
        "settings.view",
        "settings.manage",
        "team.view",
        "team.manage",
        "audit.view",
        "billing.view",
        "billing.manage",
        "integrations.manage",
    },
    "manager": {
        "leads.view",
        "leads.create",
        "leads.update",
        "contacts.view",
        "contacts.update",
        "campaigns.view",
        "campaigns.create",
        "campaigns.update",
        "campaigns.send",
        "replies.view",
        "replies.respond",
        "meetings.view",
        "meetings.manage",
        "pipeline.view",
        "pipeline.manage",
        "settings.view",
        "team.view",
    },
    "member": {
        "leads.view",
        "leads.create",
        "leads.update",
        "contacts.view",
        "contacts.update",
        "campaigns.view",
        "replies.view",
        "replies.respond",
        "meetings.view",
        "meetings.manage",
        "pipeline.view",
        "pipeline.manage",
        "settings.view",
        "team.view",
    },
    "viewer": {
        "leads.view",
        "contacts.view",
        "campaigns.view",
        "replies.view",
        "meetings.view",
        "pipeline.view",
        "settings.view",
        "team.view",
    },
}

PUBLIC_PATH_PREFIXES = (
    "/api/health",
    "/api/auth/register",
    "/api/auth/login",
    "/api/auth/refresh",
    "/api/auth/forgot-password",
    "/api/auth/reset-password",
    "/api/auth/invitations/",
    "/api/bookings/",
    "/api/unsubscribe",
    "/unsubscribe",
    "/api/webhooks/",
    "/docs",
    "/openapi.json",
    "/redoc",
)

PUBLIC_EXACT = {
    "/api/meetings/book",
    "/api/health",
    "/api/health/live",
    "/api/health/ready",
}


@dataclass(frozen=True)
class TenantContext:
    user_id: uuid.UUID
    organization_id: uuid.UUID
    role: str
    email: str
    session_id: uuid.UUID | None = None

    @property
    def permissions(self) -> set[str]:
        return set(ROLE_PERMISSIONS.get(self.role, set()))

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions


def get_current_tenant() -> TenantContext | None:
    return _tenant_ctx.get()


def set_current_tenant(ctx: TenantContext | None):
    return _tenant_ctx.set(ctx)


def reset_current_tenant(token) -> None:
    _tenant_ctx.reset(token)


def require_org_id() -> uuid.UUID:
    ctx = get_current_tenant()
    if not ctx:
        raise RuntimeError("Tenant context required")
    return ctx.organization_id


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return pwd_context.verify(password, password_hash)
    except Exception:  # noqa: BLE001
        return False


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def generate_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def _jwt_secret() -> str:
    settings = get_settings()
    secret = (settings.secret_key or "").strip()
    if not secret:
        if settings.is_production():
            raise RuntimeError("SECRET_KEY required for JWT in production")
        # Deterministic dev-only fallback — never use in production
        secret = "leadflow-dev-only-secret-change-me"
    return secret


def create_access_token(
    *,
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
    role: str,
    session_id: uuid.UUID | None = None,
) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "org": str(organization_id),
        "role": role,
        "sid": str(session_id) if session_id else None,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_access_ttl_minutes)).timestamp()),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm="HS256")


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "TOKEN_EXPIRED", "message": "Session expired. Please sign in again."}},
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "INVALID_TOKEN", "message": "Invalid authentication token."}},
        ) from exc
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "INVALID_TOKEN", "message": "Invalid authentication token."}},
        )
    return payload


def is_public_path(path: str, method: str) -> bool:
    if path in PUBLIC_EXACT:
        return True
    if path.startswith("/api/auth/invitations"):
        return True
    if path in {
        "/api/auth/register",
        "/api/auth/login",
        "/api/auth/refresh",
        "/api/auth/forgot-password",
        "/api/auth/reset-password",
        "/api/auth/logout",
    }:
        return True
    if path.startswith("/api/health"):
        return True
    if path.startswith("/api/bookings/"):
        return True
    if path == "/api/meetings/book" and method.upper() == "POST":
        return True
    if path.startswith("/api/unsubscribe") or path.startswith("/unsubscribe"):
        return True
    if path.startswith("/api/webhooks/"):
        return True
    if path in {"/docs", "/openapi.json", "/redoc"} or path.startswith("/docs"):
        return True
    return False


def resolve_membership(db: Session, user_id: uuid.UUID, organization_id: uuid.UUID) -> OrganizationMember:
    member = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.user_id == user_id,
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.status == "active",
        )
        .one_or_none()
    )
    if not member:
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "NOT_A_MEMBER", "message": "You are not a member of this organization."}},
        )
    org = db.get(Organization, organization_id)
    if not org or org.status != "active":
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "ORG_INACTIVE", "message": "Organization is not active."}},
        )
    return member


def build_tenant_from_user_org(
    db: Session, user: User, organization_id: uuid.UUID, session_id: uuid.UUID | None = None
) -> TenantContext:
    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "USER_INACTIVE", "message": "Account is inactive."}},
        )
    member = resolve_membership(db, user.id, organization_id)
    return TenantContext(
        user_id=user.id,
        organization_id=organization_id,
        role=member.role,
        email=user.email,
        session_id=session_id,
    )


def get_tenant_context(
    request: Request,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> TenantContext:
    # Prefer already-resolved context (middleware)
    existing = getattr(request.state, "tenant", None)
    if isinstance(existing, TenantContext):
        set_current_tenant(existing)
        return existing

    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "UNAUTHORIZED", "message": "Authentication required."}},
        )

    payload = decode_access_token(credentials.credentials)
    try:
        user_id = uuid.UUID(payload["sub"])
        org_id = uuid.UUID(payload["org"])
        session_id = uuid.UUID(payload["sid"]) if payload.get("sid") else None
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "INVALID_TOKEN", "message": "Invalid authentication token."}},
        ) from exc

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "UNAUTHORIZED", "message": "Authentication required."}},
        )

    if session_id:
        session = db.get(AuthSession, session_id)
        if not session or session.revoked_at is not None:
            raise HTTPException(
                status_code=401,
                detail={"error": {"code": "SESSION_REVOKED", "message": "Session is no longer valid."}},
            )
        # Ensure session org matches token (switch updates session)
        org_id = session.organization_id

    ctx = build_tenant_from_user_org(db, user, org_id, session_id=session_id)
    request.state.tenant = ctx
    set_current_tenant(ctx)
    return ctx


TenantDep = Annotated[TenantContext, Depends(get_tenant_context)]


def require_permission(permission: str) -> Callable:
    def _dep(tenant: TenantDep) -> TenantContext:
        if not tenant.has_permission(permission):
            raise HTTPException(
                status_code=403,
                detail={
                    "error": {
                        "code": "FORBIDDEN",
                        "message": "You do not have permission to perform this action.",
                    }
                },
            )
        return tenant

    return _dep


def require_role(*roles: str) -> Callable:
    allowed = set(roles)

    def _dep(tenant: TenantDep) -> TenantContext:
        if tenant.role not in allowed:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": {
                        "code": "FORBIDDEN",
                        "message": "You do not have permission to perform this action.",
                    }
                },
            )
        return tenant

    return _dep


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())
