"""Phase 13 — Billing API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.tenant import TenantDep, require_permission
from app.models.auth import User
from app.services.billing import service as billing_service

router = APIRouter(tags=["Billing"])


class CheckoutRequest(BaseModel):
    target_plan: str
    billing_interval: str = "month"
    success_url: str | None = None
    cancel_url: str | None = None


class ChangePlanRequest(BaseModel):
    target_plan: str
    billing_interval: str = "month"


class CancelRequest(BaseModel):
    cancel_at_period_end: bool = True


@router.get("/api/billing/plans", summary="List subscription plans")
def list_plans(_tenant: TenantDep) -> dict:
    """Plan catalog — available to any authenticated member (no fake pricing claims)."""
    return billing_service.plans_response()


@router.get("/api/billing/subscription", summary="Current subscription")
def get_subscription(
    tenant: TenantDep,
    db: Session = Depends(get_db),
    _perm=Depends(require_permission("billing.view")),
) -> dict:
    return billing_service.subscription_payload(db, tenant.organization_id)


@router.get("/api/billing/usage", summary="Current period usage")
def get_usage(
    tenant: TenantDep,
    db: Session = Depends(get_db),
    _perm=Depends(require_permission("billing.view")),
) -> dict:
    return billing_service.usage_response(db, tenant.organization_id)


@router.post("/api/billing/checkout", summary="Start checkout")
def checkout(
    payload: CheckoutRequest,
    tenant: TenantDep,
    db: Session = Depends(get_db),
    _perm=Depends(require_permission("billing.manage")),
) -> dict:
    settings = get_settings()
    user = db.get(User, tenant.user_id)
    if not user:
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="User not found")
    success = payload.success_url or f"{settings.frontend_url}/settings?tab=billing&checkout=success"
    cancel = payload.cancel_url or f"{settings.frontend_url}/settings?tab=billing&checkout=cancel"
    return billing_service.start_checkout(
        db,
        organization_id=tenant.organization_id,
        user=user,
        target_plan=payload.target_plan,
        billing_interval=payload.billing_interval,
        success_url=success,
        cancel_url=cancel,
    )


@router.post("/api/billing/portal", summary="Customer billing portal")
def portal(
    tenant: TenantDep,
    db: Session = Depends(get_db),
    _perm=Depends(require_permission("billing.manage")),
) -> dict:
    settings = get_settings()
    return billing_service.create_portal(
        db,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        return_url=f"{settings.frontend_url}/settings?tab=billing",
    )


@router.post("/api/billing/change-plan", summary="Change subscription plan")
def change_plan(
    payload: ChangePlanRequest,
    tenant: TenantDep,
    db: Session = Depends(get_db),
    _perm=Depends(require_permission("billing.manage")),
) -> dict:
    return billing_service.change_plan(
        db,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        target_plan=payload.target_plan,
        billing_interval=payload.billing_interval,
    )


@router.post("/api/billing/cancel", summary="Cancel subscription")
def cancel(
    payload: CancelRequest,
    tenant: TenantDep,
    db: Session = Depends(get_db),
    _perm=Depends(require_permission("billing.manage")),
) -> dict:
    return billing_service.cancel_subscription(
        db,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
        at_period_end=payload.cancel_at_period_end,
    )


@router.post("/api/billing/resume", summary="Resume subscription")
def resume(
    tenant: TenantDep,
    db: Session = Depends(get_db),
    _perm=Depends(require_permission("billing.manage")),
) -> dict:
    return billing_service.resume_subscription(
        db,
        organization_id=tenant.organization_id,
        user_id=tenant.user_id,
    )


@router.post("/api/webhooks/billing/{provider}", summary="Billing provider webhook")
async def billing_webhook(
    provider: str,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    body = await request.body()
    signature = request.headers.get("Stripe-Signature") or request.headers.get("X-Billing-Signature")
    return billing_service.handle_billing_webhook(
        db, provider_name=provider, payload=body, signature=signature
    )
