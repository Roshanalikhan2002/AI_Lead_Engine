"""Suppression list helpers."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.email_suppression import EmailSuppression


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def is_suppressed(db: Session, email: str, organization_id=None) -> EmailSuppression | None:
    q = db.query(EmailSuppression).filter(EmailSuppression.email == normalize_email(email))
    if organization_id is not None:
        q = q.filter(EmailSuppression.organization_id == organization_id)
    else:
        from app.core.tenant import get_current_tenant

        ctx = get_current_tenant()
        if ctx:
            q = q.filter(EmailSuppression.organization_id == ctx.organization_id)
    return q.one_or_none()


def add_suppression(
    db: Session,
    email: str,
    *,
    reason: str,
    source: str = "api",
    organization_id=None,
) -> EmailSuppression:
    from app.core.tenant import get_current_tenant

    oid = organization_id
    if oid is None:
        ctx = get_current_tenant()
        oid = ctx.organization_id if ctx else None
    normalized = normalize_email(email)
    existing = is_suppressed(db, normalized, organization_id=oid)
    if existing:
        if existing.reason == "unsubscribe" and reason in {"hard_bounce", "complaint"}:
            existing.reason = reason
            existing.source = source
            db.commit()
            db.refresh(existing)
        return existing
    row = EmailSuppression(organization_id=oid, email=normalized, reason=reason, source=source)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
