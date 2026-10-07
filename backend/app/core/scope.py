"""Helpers for tenant-scoped queries."""

from __future__ import annotations

import uuid
from typing import TypeVar

from fastapi import HTTPException
from sqlalchemy.orm import Query, Session

from app.core.tenant import TenantContext, get_current_tenant

T = TypeVar("T")


def org_id_or_raise(tenant: TenantContext | None = None) -> uuid.UUID:
    ctx = tenant or get_current_tenant()
    if not ctx:
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "UNAUTHORIZED", "message": "Authentication required."}},
        )
    return ctx.organization_id


def tenant_query(db: Session, model: type[T], tenant: TenantContext | None = None) -> Query:
    """Base query filtered by the active organization."""
    oid = org_id_or_raise(tenant)
    return db.query(model).filter(model.organization_id == oid)  # type: ignore[attr-defined]


def get_tenant_entity(
    db: Session,
    model: type[T],
    entity_id: uuid.UUID,
    tenant: TenantContext | None = None,
    *,
    not_found: str = "Not found",
) -> T:
    row = (
        tenant_query(db, model, tenant)
        .filter(model.id == entity_id)  # type: ignore[attr-defined]
        .one_or_none()
    )
    if not row:
        # Always 404 for cross-tenant — never leak existence
        raise HTTPException(status_code=404, detail=not_found)
    return row
