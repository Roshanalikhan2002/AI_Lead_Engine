"""Audit logging — never store secrets in metadata."""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)

SECRET_KEYS = re.compile(
    r"(api[_-]?key|secret|password|token|authorization|credential)",
    re.I,
)


def _sanitize(meta: dict[str, Any] | None) -> dict[str, Any] | None:
    if not meta:
        return None
    out: dict[str, Any] = {}
    for k, v in meta.items():
        if SECRET_KEYS.search(str(k)):
            out[k] = "[redacted]"
        elif isinstance(v, str) and len(v) > 500:
            out[k] = v[:500] + "…"
        else:
            out[k] = v
    return out


def write_audit(
    db: Session,
    *,
    action: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    actor_type: str = "system",
    actor_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    request_id: str | None = None,
    organization_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    commit: bool = True,
) -> AuditLog | None:
    row = AuditLog(
        organization_id=organization_id,
        actor_type=actor_type,
        actor_id=actor_id,
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        metadata_json=_sanitize(metadata),
        request_id=request_id,
    )
    db.add(row)
    try:
        if commit:
            db.commit()
            db.refresh(row)
        else:
            db.flush()
    except Exception:  # noqa: BLE001
        if commit:
            db.rollback()
        logger.exception("Failed to write audit log action=%s", action)
        return None
    return row
