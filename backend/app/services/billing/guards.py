"""HTTP-facing usage / feature guards."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.services.billing.features import FeatureNotAvailable, raise_http_feature, require_feature
from app.services.billing.usage import UsageLimitError, check_limit, raise_http_usage


def enforce_usage(db: Session, organization_id: uuid.UUID, resource: str, *, amount: int = 1) -> None:
    try:
        check_limit(db, organization_id, resource, amount=amount)
    except UsageLimitError as exc:
        raise_http_usage(exc)


def enforce_feature(db: Session, organization_id: uuid.UUID, feature: str) -> None:
    try:
        require_feature(db, organization_id, feature)
    except FeatureNotAvailable as exc:
        raise_http_feature(exc)
