"""Feature gating by plan."""

from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.billing.plans import get_plan
from app.services.billing.usage import resolve_plan_id


class FeatureNotAvailable(Exception):
    def __init__(self, feature: str, plan: str):
        self.feature = feature
        self.plan = plan
        super().__init__(f"Feature {feature} not available on plan {plan}")

    def http_detail(self) -> dict:
        return {
            "error": {
                "code": "FEATURE_NOT_AVAILABLE",
                "feature": self.feature,
                "plan": self.plan,
                "message": f"Your current plan ({self.plan}) does not include {self.feature.replace('_', ' ')}.",
            }
        }


def require_feature(db: Session, organization_id: uuid.UUID, feature: str) -> None:
    plan_id = resolve_plan_id(db, organization_id)
    plan = get_plan(plan_id)
    if feature not in plan.features:
        raise FeatureNotAvailable(feature, plan_id)


def raise_http_feature(exc: FeatureNotAvailable) -> None:
    raise HTTPException(status_code=403, detail=exc.http_detail()) from exc
