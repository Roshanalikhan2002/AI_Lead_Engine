"""Phase 13 — usage limits and increments."""

from __future__ import annotations

import uuid

from app.billing.plans import get_plan
from app.services.billing.usage import (
    UsageLimitError,
    check_limit,
    get_or_create_usage_period,
    get_usage_value,
    increment_usage,
    remaining_usage,
)


def test_free_plan_limits():
    plan = get_plan("free")
    assert plan.limits["ai_qualifications"] == 25
    assert plan.limits["team_members"] == 2
    assert plan.limits["active_campaigns"] == 1


def test_usage_increment_and_limit(db_session, auth_tenant):
    org_id = auth_tenant["organization_id"]
    get_or_create_usage_period(db_session, org_id)
    for _ in range(25):
        increment_usage(db_session, org_id, "ai_qualifications", amount=1)
    assert get_usage_value(db_session, org_id, "ai_qualifications") == 25
    assert remaining_usage(db_session, org_id, "ai_qualifications") == 0
    try:
        increment_usage(db_session, org_id, "ai_qualifications", amount=1)
        assert False, "expected UsageLimitError"
    except UsageLimitError as exc:
        assert exc.code == "USAGE_LIMIT_REACHED"
        assert exc.used == 25
        assert exc.limit == 25


def test_check_limit_team_members(db_session, auth_tenant):
    org_id = auth_tenant["organization_id"]
    # owner already counts as 1; free allows 2
    check_limit(db_session, org_id, "team_members", amount=1)
    # adding 2 more would exceed
    try:
        check_limit(db_session, org_id, "team_members", amount=2)
        assert False, "expected limit"
    except UsageLimitError as exc:
        assert exc.code == "TEAM_MEMBER_LIMIT_REACHED"


def test_enterprise_unlimited(db_session, auth_tenant):
    from app.models.auth import Organization
    from app.services.billing.service import ensure_free_subscription

    org = db_session.get(Organization, auth_tenant["organization_id"])
    org.plan = "enterprise"
    sub = ensure_free_subscription(db_session, auth_tenant["organization_id"])
    sub.plan = "enterprise"
    sub.status = "active"
    db_session.commit()
    for _ in range(50):
        increment_usage(db_session, auth_tenant["organization_id"], "ai_qualifications", amount=1)
    assert get_usage_value(db_session, auth_tenant["organization_id"], "ai_qualifications") == 50


def test_no_usage_reset_api(client):
    res = client.post("/api/billing/usage/reset")
    assert res.status_code in {404, 405}
    res2 = client.delete("/api/billing/usage")
    assert res2.status_code in {404, 405}
