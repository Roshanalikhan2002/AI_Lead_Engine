"""Optional auth dependency for router-wide enforcement."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.tenant import TenantContext, get_tenant_context, is_public_path, set_current_tenant

bearer_optional = HTTPBearer(auto_error=False)


def enforce_auth_dependency(
    request: Request,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_optional),
) -> TenantContext | None:
    """Require auth for all non-public API paths."""
    settings = get_settings()
    path = request.url.path
    method = request.method.upper()

    if not settings.auth_required:
        return None

    if is_public_path(path, method):
        return None

    # Special-case logout: allow without valid token
    if path == "/api/auth/logout":
        try:
            if credentials:
                return get_tenant_context(request, db, credentials)
        except HTTPException:
            return None
        return None

    return get_tenant_context(request, db, credentials)


def bind_tenant_context(request: Request) -> TenantContext | None:
    """Re-bind ContextVar in the worker thread handling the route (sync routes)."""
    tenant = getattr(request.state, "tenant", None)
    if isinstance(tenant, TenantContext):
        set_current_tenant(tenant)
        return tenant
    return None
