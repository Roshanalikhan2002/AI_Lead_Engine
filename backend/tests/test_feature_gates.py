"""Phase 13 — feature gating."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.services.billing.features import FeatureNotAvailable, require_feature, raise_http_feature
from app.services.billing.service import ensure_free_subscription


def test_free_has_core_features(db_session, auth_tenant):
    org_id = auth_tenant["organization_id"]
    ensure_free_subscription(db_session, org_id)
    require_feature(db_session, org_id, "ai_qualification")
    require_feature(db_session, org_id, "campaigns")


def test_free_lacks_advanced_analytics(db_session, auth_tenant):
    org_id = auth_tenant["organization_id"]
    with pytest.raises(FeatureNotAvailable) as exc:
        require_feature(db_session, org_id, "advanced_analytics")
    assert exc.value.feature == "advanced_analytics"
    with pytest.raises(HTTPException) as http_exc:
        raise_http_feature(exc.value)
    assert http_exc.value.status_code == 403
    assert http_exc.value.detail["error"]["code"] == "FEATURE_NOT_AVAILABLE"


def test_growth_has_advanced_analytics(db_session, auth_tenant):
    from app.models.auth import Organization

    org_id = auth_tenant["organization_id"]
    org = db_session.get(Organization, org_id)
    org.plan = "growth"
    sub = ensure_free_subscription(db_session, org_id)
    sub.plan = "growth"
    sub.status = "active"
    db_session.commit()
    require_feature(db_session, org_id, "advanced_analytics")
