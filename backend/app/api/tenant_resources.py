"""Shared tenant-scoped lead lookup for legacy routes."""

from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.tenant import TenantContext, get_current_tenant
from app.models.lead import Lead


def resolve_organization_id(tenant: TenantContext | None = None) -> uuid.UUID:
    if tenant is not None:
        return tenant.organization_id
    ctx = get_current_tenant()
    if ctx is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return ctx.organization_id


def get_org_lead_or_404(
    db: Session,
    lead_id: uuid.UUID,
    organization_id: uuid.UUID | None = None,
    *,
    tenant: TenantContext | None = None,
) -> Lead:
    oid = organization_id
    if oid is None:
        oid = resolve_organization_id(tenant)
    lead = (
        db.query(Lead)
        .filter(Lead.id == lead_id, Lead.organization_id == oid)
        .one_or_none()
    )
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead
