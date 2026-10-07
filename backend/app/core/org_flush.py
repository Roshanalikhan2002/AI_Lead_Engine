"""Assign organization_id on flush when missing (tenant context or test seed)."""

from __future__ import annotations

import uuid
from contextvars import ContextVar

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.core.tenant import get_current_tenant

_fallback_org: ContextVar[uuid.UUID | None] = ContextVar("fallback_org_id", default=None)


def set_fallback_organization_id(organization_id: uuid.UUID | None):
    return _fallback_org.set(organization_id)


def reset_fallback_organization_id(token) -> None:
    _fallback_org.reset(token)


def _resolve_org_id() -> uuid.UUID | None:
    ctx = get_current_tenant()
    if ctx:
        return ctx.organization_id
    return _fallback_org.get()


@event.listens_for(Session, "before_flush")
def assign_organization_id(session: Session, _flush_context, _instances) -> None:
    org_id = _resolve_org_id()
    if org_id is None:
        return
    for obj in session.new:
        if hasattr(obj, "organization_id") and getattr(obj, "organization_id", None) is None:
            try:
                setattr(obj, "organization_id", org_id)
            except Exception:  # noqa: BLE001
                pass
