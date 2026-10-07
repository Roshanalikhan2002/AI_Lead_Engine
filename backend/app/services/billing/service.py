"""Billing orchestration — subscriptions, checkout, portal, webhooks."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.billing.plans import get_plan, list_plans_public
from app.core.config import get_settings
from app.models.auth import Organization, User
from app.models.billing import BillingCustomer, BillingWebhookEvent, Subscription
from app.services.billing.providers import (
    BillingProviderError,
    get_billing_provider,
)
from app.services.billing.usage import get_or_create_usage_period, usage_snapshot
from app.services.system.audit import write_audit

PAID_PLANS = {"starter", "growth", "agency", "enterprise"}
PLAN_RANK = {"free": 0, "starter": 1, "growth": 2, "agency": 3, "enterprise": 4}


def ensure_free_subscription(db: Session, organization_id: uuid.UUID) -> Subscription:
    existing = (
        db.query(Subscription)
        .filter(Subscription.organization_id == organization_id)
        .order_by(Subscription.created_at.desc())
        .first()
    )
    if existing:
        return existing
    now = datetime.now(timezone.utc)
    sub = Subscription(
        organization_id=organization_id,
        provider="unconfigured",
        plan="free",
        status="active",
        billing_interval="month",
        current_period_start=now.replace(day=1, hour=0, minute=0, second=0, microsecond=0),
        current_period_end=None,
    )
    db.add(sub)
    get_or_create_usage_period(db, organization_id)
    db.commit()
    db.refresh(sub)
    return sub


def get_subscription_for_org(db: Session, organization_id: uuid.UUID) -> Subscription:
    return ensure_free_subscription(db, organization_id)


def subscription_payload(db: Session, organization_id: uuid.UUID) -> dict[str, Any]:
    org = db.get(Organization, organization_id)
    sub = get_subscription_for_org(db, organization_id)
    settings = get_settings()
    provider = get_billing_provider()
    plan = get_plan(sub.plan or (org.plan if org else "free"))
    grace_warning = False
    if sub.status == "past_due" and sub.grace_period_ends_at:
        gp = sub.grace_period_ends_at
        if gp.tzinfo is None:
            gp = gp.replace(tzinfo=timezone.utc)
        grace_warning = gp >= datetime.now(timezone.utc)

    return {
        "organization_id": str(organization_id),
        "plan": sub.plan,
        "organization_plan": org.plan if org else "free",
        "status": sub.status,
        "provider": sub.provider,
        "billing_interval": sub.billing_interval,
        "trial_start": sub.trial_start.isoformat() if sub.trial_start else None,
        "trial_end": sub.trial_end.isoformat() if sub.trial_end else None,
        "current_period_start": sub.current_period_start.isoformat() if sub.current_period_start else None,
        "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
        "cancel_at_period_end": sub.cancel_at_period_end,
        "cancelled_at": sub.cancelled_at.isoformat() if sub.cancelled_at else None,
        "grace_period_ends_at": sub.grace_period_ends_at.isoformat() if sub.grace_period_ends_at else None,
        "grace_warning": grace_warning,
        "plan_name": plan.name,
        "features": sorted(plan.features),
        "billing_provider_configured": provider.name not in {"unconfigured", ""},
        "billing_provider_name": provider.name,
        "billing_test_mode": bool(settings.billing_test_mode),
        "external_customer_id": sub.external_customer_id,
        "external_subscription_id": sub.external_subscription_id,
    }


def _get_or_create_customer(
    db: Session, *, organization_id: uuid.UUID, provider_name: str, email: str, org_name: str
) -> BillingCustomer:
    row = (
        db.query(BillingCustomer)
        .filter(
            BillingCustomer.organization_id == organization_id,
            BillingCustomer.provider == provider_name,
        )
        .one_or_none()
    )
    if row and row.external_customer_id:
        return row
    provider = get_billing_provider()
    try:
        external_id = provider.create_customer(
            organization_id=str(organization_id), email=email, name=org_name
        )
    except BillingProviderError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"error": {"code": exc.code, "message": str(exc)}},
        ) from exc
    if row:
        row.external_customer_id = external_id
        db.add(row)
    else:
        row = BillingCustomer(
            organization_id=organization_id,
            provider=provider_name,
            external_customer_id=external_id,
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    return row


def start_checkout(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user: User,
    target_plan: str,
    billing_interval: str,
    success_url: str,
    cancel_url: str,
) -> dict[str, Any]:
    plan_id = (target_plan or "").strip().lower()
    if plan_id not in PAID_PLANS:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "INVALID_PLAN", "message": "Choose a paid plan to checkout."}},
        )
    interval = (billing_interval or "month").strip().lower()
    if interval not in {"month", "year"}:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "INVALID_INTERVAL", "message": "billing_interval must be month or year."}},
        )
    if plan_id == "enterprise":
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "CONTACT_SALES",
                    "message": "Enterprise plans require Contact Sales — checkout is not available.",
                }
            },
        )

    provider = get_billing_provider()
    org = db.get(Organization, organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    if provider.name == "unconfigured":
        write_audit(
            db,
            action="checkout_blocked",
            entity_type="organization",
            entity_id=str(organization_id),
            organization_id=organization_id,
            actor_user_id=user.id,
            metadata={"plan": plan_id, "reason": "provider_unconfigured"},
            commit=True,
        )
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": "BILLING_NOT_CONFIGURED",
                    "message": "Billing provider is not configured.",
                }
            },
        )

    customer = _get_or_create_customer(
        db,
        organization_id=organization_id,
        provider_name=provider.name,
        email=user.email,
        org_name=org.name,
    )
    result = provider.create_checkout_session(
        customer_id=customer.external_customer_id,
        organization_id=str(organization_id),
        plan=plan_id,
        billing_interval=interval,
        success_url=success_url,
        cancel_url=cancel_url,
    )
    write_audit(
        db,
        action="checkout_started",
        entity_type="organization",
        entity_id=str(organization_id),
        organization_id=organization_id,
        actor_user_id=user.id,
        metadata={
            "plan": plan_id,
            "interval": interval,
            "provider": provider.name,
            "mode": result.mode,
            "session_id": result.session_id,
        },
        commit=True,
    )
    return {
        "provider": result.provider,
        "mode": result.mode,
        "checkout_url": result.checkout_url,
        "session_id": result.session_id,
        "message": result.message,
    }


def create_portal(
    db: Session, *, organization_id: uuid.UUID, user_id: uuid.UUID, return_url: str
) -> dict[str, Any]:
    provider = get_billing_provider()
    if provider.name == "unconfigured":
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": "BILLING_NOT_CONFIGURED",
                    "message": "Billing provider is not configured.",
                }
            },
        )
    customer = (
        db.query(BillingCustomer)
        .filter(
            BillingCustomer.organization_id == organization_id,
            BillingCustomer.provider == provider.name,
        )
        .one_or_none()
    )
    if not customer or not customer.external_customer_id:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "NO_BILLING_CUSTOMER",
                    "message": "No billing customer exists for this organization.",
                }
            },
        )
    result = provider.create_portal_session(
        customer_id=customer.external_customer_id, return_url=return_url
    )
    write_audit(
        db,
        action="billing_portal_opened",
        entity_type="organization",
        entity_id=str(organization_id),
        organization_id=organization_id,
        actor_user_id=user_id,
        metadata={"provider": provider.name, "mode": result.mode},
        commit=True,
    )
    return {
        "provider": result.provider,
        "mode": result.mode,
        "portal_url": result.portal_url,
        "message": result.message,
    }


def change_plan(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    target_plan: str,
    billing_interval: str = "month",
) -> dict[str, Any]:
    plan_id = (target_plan or "").strip().lower()
    if plan_id not in {"free", *PAID_PLANS}:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "INVALID_PLAN", "message": f"Unknown plan: {target_plan}"}},
        )
    interval = (billing_interval or "month").strip().lower()
    provider = get_billing_provider()
    sub = get_subscription_for_org(db, organization_id)
    org = db.get(Organization, organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Downgrade to free without provider when already free/mock/unconfigured
    if plan_id == "free":
        sub.plan = "free"
        sub.status = "active"
        sub.cancel_at_period_end = False
        sub.provider = sub.provider or "unconfigured"
        org.plan = "free"
        db.add(sub)
        db.add(org)
        write_audit(
            db,
            action="plan_changed",
            entity_type="subscription",
            entity_id=str(sub.id),
            organization_id=organization_id,
            actor_user_id=user_id,
            metadata={"plan": "free", "provider": provider.name},
            commit=True,
        )
        return subscription_payload(db, organization_id)

    if provider.name == "unconfigured":
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": "BILLING_NOT_CONFIGURED",
                    "message": "Billing provider is not configured.",
                }
            },
        )

    # Mock (or live) provider plan change
    customer = _get_or_create_customer(
        db,
        organization_id=organization_id,
        provider_name=provider.name,
        email="",
        org_name=org.name,
    )
    try:
        if sub.external_subscription_id:
            result = provider.change_plan(
                subscription_id=sub.external_subscription_id,
                plan=plan_id,
                billing_interval=interval,
            )
        else:
            result = provider.create_subscription(
                customer_id=customer.external_customer_id or f"cus_{organization_id}",
                plan=plan_id,
                billing_interval=interval,
            )
    except BillingProviderError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"error": {"code": exc.code, "message": str(exc)}},
        ) from exc

    _apply_provider_subscription(db, org, sub, result, provider_name=provider.name)
    write_audit(
        db,
        action="plan_changed",
        entity_type="subscription",
        entity_id=str(sub.id),
        organization_id=organization_id,
        actor_user_id=user_id,
        metadata={
            "plan": plan_id,
            "previous_rank": PLAN_RANK.get(sub.plan, 0),
            "provider": provider.name,
            "mode": "mock" if provider.name == "mock" else "provider",
        },
        commit=True,
    )
    return subscription_payload(db, organization_id)


def cancel_subscription(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    at_period_end: bool = True,
) -> dict[str, Any]:
    provider = get_billing_provider()
    sub = get_subscription_for_org(db, organization_id)
    org = db.get(Organization, organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    if sub.plan == "free" and not sub.external_subscription_id:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "NOTHING_TO_CANCEL", "message": "Free plan has no paid subscription."}},
        )

    if provider.name != "unconfigured" and sub.external_subscription_id:
        try:
            result = provider.cancel_subscription(
                subscription_id=sub.external_subscription_id, at_period_end=at_period_end
            )
            sub.cancel_at_period_end = result.cancel_at_period_end
            if result.status == "cancelled":
                sub.status = "cancelled"
                sub.cancelled_at = datetime.now(timezone.utc)
                # Preserve access until period end when cancel_at_period_end
            else:
                sub.status = result.status
                sub.cancel_at_period_end = True if at_period_end else False
        except BillingProviderError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail={"error": {"code": exc.code, "message": str(exc)}},
            ) from exc
    else:
        sub.cancel_at_period_end = at_period_end
        if at_period_end:
            sub.status = "active"
        else:
            sub.status = "cancelled"
            sub.cancelled_at = datetime.now(timezone.utc)
            org.plan = "free"
            sub.plan = "free"

    db.add(sub)
    db.add(org)
    write_audit(
        db,
        action="subscription_cancelled",
        entity_type="subscription",
        entity_id=str(sub.id),
        organization_id=organization_id,
        actor_user_id=user_id,
        metadata={"at_period_end": at_period_end, "provider": provider.name},
        commit=True,
    )
    return subscription_payload(db, organization_id)


def resume_subscription(
    db: Session, *, organization_id: uuid.UUID, user_id: uuid.UUID
) -> dict[str, Any]:
    provider = get_billing_provider()
    sub = get_subscription_for_org(db, organization_id)
    if not sub.cancel_at_period_end:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "NOT_SCHEDULED_FOR_CANCEL",
                    "message": "Subscription is not scheduled for cancellation.",
                }
            },
        )
    if provider.name != "unconfigured" and sub.external_subscription_id:
        try:
            result = provider.resume_subscription(subscription_id=sub.external_subscription_id)
            sub.cancel_at_period_end = result.cancel_at_period_end
            sub.status = result.status
        except BillingProviderError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail={"error": {"code": exc.code, "message": str(exc)}},
            ) from exc
    else:
        sub.cancel_at_period_end = False
        sub.status = "active"
        sub.cancelled_at = None

    db.add(sub)
    write_audit(
        db,
        action="subscription_resumed",
        entity_type="subscription",
        entity_id=str(sub.id),
        organization_id=organization_id,
        actor_user_id=user_id,
        metadata={"provider": provider.name},
        commit=True,
    )
    return subscription_payload(db, organization_id)


def _apply_provider_subscription(
    db: Session,
    org: Organization,
    sub: Subscription,
    result: Any,
    *,
    provider_name: str,
) -> None:
    sub.provider = provider_name
    sub.external_customer_id = result.external_customer_id
    sub.external_subscription_id = result.external_subscription_id
    sub.plan = result.plan
    sub.status = result.status
    sub.billing_interval = result.billing_interval
    sub.current_period_start = result.current_period_start
    sub.current_period_end = result.current_period_end
    sub.cancel_at_period_end = result.cancel_at_period_end
    sub.trial_end = result.trial_end
    if result.status in {"active", "trialing"}:
        org.plan = result.plan
    db.add(sub)
    db.add(org)
    db.commit()
    db.refresh(sub)


def resolve_org_from_customer(
    db: Session, *, provider: str, external_customer_id: str | None
) -> uuid.UUID | None:
    if not external_customer_id:
        return None
    row = (
        db.query(BillingCustomer)
        .filter(
            BillingCustomer.provider == provider,
            BillingCustomer.external_customer_id == external_customer_id,
        )
        .one_or_none()
    )
    return row.organization_id if row else None


def handle_billing_webhook(
    db: Session,
    *,
    provider_name: str,
    payload: bytes,
    signature: str | None,
) -> dict[str, Any]:
    # Only process for the configured provider (or mock in test)
    configured = get_billing_provider()
    name = (provider_name or "").strip().lower()
    if name not in {configured.name, "mock", "stripe"}:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "UNKNOWN_PROVIDER", "message": f"Unknown billing provider: {name}"}},
        )

    if name == "mock":
        from app.services.billing.providers import MockBillingProvider

        verifier: Any = MockBillingProvider()
    elif name == "stripe" and configured.name == "stripe":
        verifier = configured
    elif name == configured.name:
        verifier = configured
    else:
        # Allow mock webhooks in non-production even if provider is unconfigured (tests)
        settings = get_settings()
        if name == "mock" and not settings.is_production():
            from app.services.billing.providers import MockBillingProvider

            verifier = MockBillingProvider()
        else:
            raise HTTPException(
                status_code=503,
                detail={"error": {"code": "BILLING_NOT_CONFIGURED", "message": "Provider mismatch."}},
            )

    try:
        event = verifier.verify_webhook(payload, signature)
    except BillingProviderError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"error": {"code": exc.code, "message": "Webhook verification failed."}},
        ) from exc

    external_event_id = str(event.get("id") or event.get("event_id") or "")
    event_type = str(event.get("type") or event.get("event_type") or "unknown")
    if not external_event_id:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "MISSING_EVENT_ID", "message": "Webhook event id required."}},
        )

    # Idempotency insert
    existing = (
        db.query(BillingWebhookEvent)
        .filter(
            BillingWebhookEvent.provider == name,
            BillingWebhookEvent.external_event_id == external_event_id,
        )
        .one_or_none()
    )
    if existing and existing.processed:
        return {"ok": True, "duplicate": True, "event_id": external_event_id}

    if not existing:
        existing = BillingWebhookEvent(
            provider=name,
            external_event_id=external_event_id,
            event_type=event_type,
            processed=False,
            payload_summary={"type": event_type},
        )
        db.add(existing)
        try:
            db.commit()
            db.refresh(existing)
        except IntegrityError:
            db.rollback()
            existing = (
                db.query(BillingWebhookEvent)
                .filter(
                    BillingWebhookEvent.provider == name,
                    BillingWebhookEvent.external_event_id == external_event_id,
                )
                .one()
            )
            if existing.processed:
                return {"ok": True, "duplicate": True, "event_id": external_event_id}

    data = event.get("data") or {}
    customer_id = data.get("customer_id") or data.get("customer")
    # Never trust organization_id from body unless also present in verified metadata after customer resolve
    org_id = resolve_org_from_customer(db, provider=name, external_customer_id=customer_id)
    if not org_id and data.get("organization_id"):
        # Only accept org id when nested under verified metadata AND customer already maps
        # — reject unverified org claims
        org_id = None

    try:
        _apply_webhook_event(db, provider=name, event_type=event_type, data=data, organization_id=org_id)
        existing.processed = True
        existing.processed_at = datetime.now(timezone.utc)
        existing.organization_id = org_id
        existing.error = None
        db.add(existing)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        existing.error = str(exc)[:500]
        db.add(existing)
        db.commit()
        raise HTTPException(
            status_code=500,
            detail={"error": {"code": "WEBHOOK_PROCESSING_FAILED", "message": "Failed to process event."}},
        ) from exc

    return {"ok": True, "duplicate": False, "event_id": external_event_id, "type": event_type}


def _apply_webhook_event(
    db: Session,
    *,
    provider: str,
    event_type: str,
    data: dict[str, Any],
    organization_id: uuid.UUID | None,
) -> None:
    if not organization_id:
        # Cannot mutate tenant state without resolved org
        return

    org = db.get(Organization, organization_id)
    sub = get_subscription_for_org(db, organization_id)
    settings = get_settings()
    now = datetime.now(timezone.utc)

    if event_type in {
        "checkout.session.completed",
        "customer.subscription.created",
        "subscription.created",
        "invoice.paid",
    }:
        plan = (data.get("plan") or sub.plan or "starter").lower()
        sub.plan = plan
        sub.status = "active" if event_type != "customer.subscription.created" or not data.get("trialing") else "trialing"
        if data.get("trialing") or event_type == "customer.subscription.trialing":
            sub.status = "trialing"
            if data.get("trial_end"):
                sub.trial_end = datetime.fromisoformat(str(data["trial_end"]).replace("Z", "+00:00"))
        sub.provider = provider
        sub.external_customer_id = data.get("customer_id") or sub.external_customer_id
        sub.external_subscription_id = data.get("subscription_id") or sub.external_subscription_id
        sub.current_period_start = now
        sub.current_period_end = now + timedelta(days=30)
        sub.cancel_at_period_end = False
        sub.grace_period_ends_at = None
        if org:
            org.plan = plan
        write_audit(
            db,
            action="subscription_created" if "created" in event_type or "checkout" in event_type else "invoice_paid",
            entity_type="subscription",
            entity_id=str(sub.id),
            organization_id=organization_id,
            metadata={"event_type": event_type, "plan": plan, "provider": provider},
            commit=False,
        )
    elif event_type in {"customer.subscription.updated", "subscription.updated"}:
        if data.get("plan"):
            sub.plan = str(data["plan"]).lower()
            if org:
                org.plan = sub.plan
        if data.get("status"):
            sub.status = str(data["status"]).lower()
        sub.cancel_at_period_end = bool(data.get("cancel_at_period_end", sub.cancel_at_period_end))
        write_audit(
            db,
            action="plan_changed",
            entity_type="subscription",
            entity_id=str(sub.id),
            organization_id=organization_id,
            metadata={"event_type": event_type, "plan": sub.plan, "provider": provider},
            commit=False,
        )
    elif event_type in {"customer.subscription.deleted", "subscription.cancelled", "subscription.canceled"}:
        sub.status = "cancelled"
        sub.cancelled_at = now
        sub.cancel_at_period_end = False
        if org:
            org.plan = "free"
        sub.plan = "free"
        write_audit(
            db,
            action="subscription_cancelled",
            entity_type="subscription",
            entity_id=str(sub.id),
            organization_id=organization_id,
            metadata={"event_type": event_type, "provider": provider},
            commit=False,
        )
    elif event_type in {"invoice.payment_failed", "payment_failed"}:
        sub.status = "past_due"
        grace = max(0, int(settings.billing_grace_period_days or 0))
        sub.grace_period_ends_at = now + timedelta(days=grace)
        write_audit(
            db,
            action="payment_failed",
            entity_type="subscription",
            entity_id=str(sub.id),
            organization_id=organization_id,
            metadata={"event_type": event_type, "grace_days": grace, "provider": provider},
            commit=False,
        )
    db.add(sub)
    if org:
        db.add(org)
    db.flush()


def plans_response() -> dict[str, Any]:
    return {"plans": list_plans_public()}


def usage_response(db: Session, organization_id: uuid.UUID) -> dict[str, Any]:
    ensure_free_subscription(db, organization_id)
    snap = usage_snapshot(db, organization_id)
    snap["subscription"] = subscription_payload(db, organization_id)
    return snap
