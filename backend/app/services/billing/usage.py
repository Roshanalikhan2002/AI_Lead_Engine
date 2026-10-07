"""Usage periods, limits, and concurrency-safe increments."""

from __future__ import annotations

import uuid
from calendar import monthrange
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.billing.plans import CAPACITY_RESOURCES, USAGE_RESOURCES, get_plan
from app.core.config import get_settings
from app.models.auth import Organization, OrganizationMember
from app.models.billing import Subscription, UsagePeriod
from app.models.campaign import Campaign
from app.services.system.audit import write_audit


class UsageLimitError(Exception):
    def __init__(
        self,
        resource: str,
        *,
        limit: int,
        used: int,
        code: str = "USAGE_LIMIT_REACHED",
    ):
        self.resource = resource
        self.limit = limit
        self.used = used
        self.remaining = max(0, limit - used)
        self.code = code
        super().__init__(f"Usage limit reached for {resource}")

    def http_detail(self) -> dict:
        return {
            "error": {
                "code": self.code,
                "resource": self.resource,
                "limit": self.limit,
                "used": self.used,
                "remaining": self.remaining,
                "message": f"You've reached your monthly {self.resource.replace('_', ' ')} limit.",
            }
        }


def _month_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    now = now or datetime.now(timezone.utc)
    start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    last = monthrange(now.year, now.month)[1]
    end = datetime(now.year, now.month, last, 23, 59, 59, tzinfo=timezone.utc)
    return start, end


def get_or_create_usage_period(
    db: Session, organization_id: uuid.UUID, *, now: datetime | None = None
) -> UsagePeriod:
    start, end = _month_window(now)
    row = (
        db.query(UsagePeriod)
        .filter(
            UsagePeriod.organization_id == organization_id,
            UsagePeriod.period_start == start,
            UsagePeriod.period_end == end,
        )
        .one_or_none()
    )
    if row:
        return row
    row = UsagePeriod(
        organization_id=organization_id,
        period_start=start,
        period_end=end,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def resolve_plan_id(db: Session, organization_id: uuid.UUID) -> str:
    org = db.get(Organization, organization_id)
    if not org:
        return "free"
    sub = (
        db.query(Subscription)
        .filter(Subscription.organization_id == organization_id)
        .order_by(Subscription.created_at.desc())
        .first()
    )
    if sub and sub.status in {"active", "trialing"}:
        return (sub.plan or org.plan or "free").lower()
    if sub and sub.status == "past_due":
        # grace period may still allow access
        if sub.grace_period_ends_at:
            gp = sub.grace_period_ends_at
            if gp.tzinfo is None:
                gp = gp.replace(tzinfo=timezone.utc)
            if gp >= datetime.now(timezone.utc):
                return (sub.plan or org.plan or "free").lower()
        return "free"
    return (org.plan or "free").lower()


def get_limit(db: Session, organization_id: uuid.UUID, resource: str) -> int | None:
    plan = get_plan(resolve_plan_id(db, organization_id))
    return plan.limits.get(resource)


def get_usage_value(db: Session, organization_id: uuid.UUID, resource: str) -> int:
    if resource in CAPACITY_RESOURCES:
        return _capacity_used(db, organization_id, resource)
    period = get_or_create_usage_period(db, organization_id)
    return int(getattr(period, resource, 0) or 0)


def _capacity_used(db: Session, organization_id: uuid.UUID, resource: str) -> int:
    if resource == "team_members":
        return (
            db.query(OrganizationMember)
            .filter(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.status == "active",
            )
            .count()
        )
    if resource == "active_campaigns":
        return (
            db.query(Campaign)
            .filter(Campaign.organization_id == organization_id, Campaign.status == "active")
            .count()
        )
    if resource == "campaign_recipients":
        from app.models.campaign_recipient import CampaignRecipient

        return (
            db.query(CampaignRecipient)
            .join(Campaign, Campaign.id == CampaignRecipient.campaign_id)
            .filter(
                Campaign.organization_id == organization_id,
                CampaignRecipient.status.in_(["pending", "active", "paused"]),
            )
            .count()
        )
    return 0


def remaining_usage(db: Session, organization_id: uuid.UUID, resource: str) -> int | None:
    limit = get_limit(db, organization_id, resource)
    if limit is None:
        return None
    used = get_usage_value(db, organization_id, resource)
    return max(0, limit - used)


def check_limit(db: Session, organization_id: uuid.UUID, resource: str, *, amount: int = 1) -> None:
    from app.services.system.test_org import is_provider_test_org

    if is_provider_test_org(db, organization_id):
        return
    plan = get_plan(resolve_plan_id(db, organization_id))
    limit = plan.limits.get(resource)
    if limit is None:
        return
    used = get_usage_value(db, organization_id, resource)
    if used + amount > limit:
        code = "USAGE_LIMIT_REACHED"
        if resource == "team_members":
            code = "TEAM_MEMBER_LIMIT_REACHED"
        elif resource == "active_campaigns":
            code = "CAMPAIGN_LIMIT_REACHED"
        raise UsageLimitError(resource, limit=limit, used=used, code=code)


def increment_usage(
    db: Session,
    organization_id: uuid.UUID,
    resource: str,
    *,
    amount: int = 1,
    check: bool = True,
    provider_test: bool = False,
) -> UsagePeriod:
    """Concurrency-safe period counter increment. Capacity resources are not incremented here.

    Provider health / isolated provider-test org operations never consume customer usage.
    """
    from app.services.system.test_org import is_provider_test_org

    if provider_test or is_provider_test_org(db, organization_id):
        return get_or_create_usage_period(db, organization_id)

    if resource in CAPACITY_RESOURCES:
        if check:
            check_limit(db, organization_id, resource, amount=amount)
        return get_or_create_usage_period(db, organization_id)

    if resource not in USAGE_RESOURCES:
        raise ValueError(f"Unknown usage resource: {resource}")

    plan = get_plan(resolve_plan_id(db, organization_id))
    limit = plan.limits.get(resource)
    period = get_or_create_usage_period(db, organization_id)
    col = getattr(UsagePeriod, resource)

    if limit is None:
        db.execute(
            update(UsagePeriod)
            .where(UsagePeriod.id == period.id)
            .values(**{resource: col + amount})
        )
        db.commit()
        db.refresh(period)
        return period

    # Atomic: only update if used + amount <= limit
    result = db.execute(
        update(UsagePeriod)
        .where(UsagePeriod.id == period.id, col + amount <= limit)
        .values(**{resource: col + amount})
    )
    db.commit()
    if result.rowcount == 0:  # type: ignore[attr-defined]
        db.refresh(period)
        used = int(getattr(period, resource, 0) or 0)
        if check or used + amount > limit:
            write_audit(
                db,
                action="usage_limit_reached",
                entity_type="usage_period",
                entity_id=str(period.id),
                organization_id=organization_id,
                metadata={"resource": resource, "limit": limit, "used": used},
                commit=True,
            )
            raise UsageLimitError(resource, limit=limit, used=used)
        # Soft path — still denied for hard plans
        raise UsageLimitError(resource, limit=limit, used=used)

    db.refresh(period)
    # Keep legacy OrganizationUsage roughly in sync for older callers
    try:
        from app.services.auth.service import bump_usage

        bump_usage(db, organization_id, resource, amount)
    except Exception:  # noqa: BLE001
        pass
    return period


def usage_snapshot(db: Session, organization_id: uuid.UUID) -> dict[str, Any]:
    plan_id = resolve_plan_id(db, organization_id)
    plan = get_plan(plan_id)
    period = get_or_create_usage_period(db, organization_id)
    items = []
    for key in list(USAGE_RESOURCES) + list(CAPACITY_RESOURCES):
        used = get_usage_value(db, organization_id, key)
        limit = plan.limits.get(key)
        pct = None
        if limit and limit > 0:
            pct = round(min(100.0, (used / limit) * 100), 1)
        items.append(
            {
                "resource": key,
                "used": used,
                "limit": limit,
                "remaining": None if limit is None else max(0, limit - used),
                "percent": pct,
                "unlimited": limit is None,
            }
        )
    return {
        "plan": plan_id,
        "plan_name": plan.name,
        "period_start": period.period_start.isoformat(),
        "period_end": period.period_end.isoformat(),
        "items": items,
    }


def raise_http_usage(exc: UsageLimitError) -> None:
    raise HTTPException(status_code=402, detail=exc.http_detail()) from exc
