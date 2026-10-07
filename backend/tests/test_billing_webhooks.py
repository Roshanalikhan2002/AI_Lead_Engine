"""Phase 13 — billing webhook signature + idempotency."""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid

from app.core.config import get_settings
from app.models.billing import BillingCustomer, BillingWebhookEvent, Subscription
from app.services.billing.service import ensure_free_subscription


def _sign(payload: bytes, secret: str = "mock_webhook_secret") -> str:
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def test_fake_webhook_rejected(client, monkeypatch):
    monkeypatch.setenv("BILLING_PROVIDER", "mock")
    get_settings.cache_clear()
    payload = json.dumps({"id": "evt_1", "type": "invoice.paid", "data": {}}).encode()
    res = client.post(
        "/api/webhooks/billing/mock",
        content=payload,
        headers={"X-Billing-Signature": "bad"},
    )
    assert res.status_code == 401


def test_webhook_idempotent_and_updates_plan(client, db_session, auth_tenant, monkeypatch):
    monkeypatch.setenv("BILLING_PROVIDER", "mock")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "mock_webhook_secret")
    get_settings.cache_clear()

    org_id = auth_tenant["organization_id"]
    ensure_free_subscription(db_session, org_id)
    customer = BillingCustomer(
        organization_id=org_id,
        provider="mock",
        external_customer_id="cus_mock_wh",
    )
    db_session.add(customer)
    db_session.commit()

    body = {
        "id": "evt_unique_1",
        "type": "checkout.session.completed",
        "data": {
            "customer_id": "cus_mock_wh",
            "plan": "starter",
            "subscription_id": "sub_mock_wh",
            # unverified org claim must be ignored
            "organization_id": str(uuid.uuid4()),
        },
    }
    raw = json.dumps(body).encode()
    sig = _sign(raw)
    headers = {"X-Billing-Signature": f"mock={sig}", "Content-Type": "application/json"}

    first = client.post("/api/webhooks/billing/mock", content=raw, headers=headers)
    assert first.status_code == 200
    assert first.json()["duplicate"] is False

    db_session.expire_all()
    sub = (
        db_session.query(Subscription)
        .filter(Subscription.organization_id == org_id)
        .order_by(Subscription.created_at.desc())
        .first()
    )
    assert sub.plan == "starter"
    assert sub.status == "active"

    second = client.post("/api/webhooks/billing/mock", content=raw, headers=headers)
    assert second.status_code == 200
    assert second.json()["duplicate"] is True
    assert (
        db_session.query(BillingWebhookEvent)
        .filter(BillingWebhookEvent.external_event_id == "evt_unique_1")
        .count()
        == 1
    )


def test_payment_failed_sets_past_due_grace(client, db_session, auth_tenant, monkeypatch):
    monkeypatch.setenv("BILLING_PROVIDER", "mock")
    monkeypatch.setenv("BILLING_GRACE_PERIOD_DAYS", "5")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "mock_webhook_secret")
    get_settings.cache_clear()

    org_id = auth_tenant["organization_id"]
    ensure_free_subscription(db_session, org_id)
    db_session.add(
        BillingCustomer(organization_id=org_id, provider="mock", external_customer_id="cus_fail")
    )
    db_session.commit()

    body = {
        "id": "evt_fail_1",
        "type": "invoice.payment_failed",
        "data": {"customer_id": "cus_fail", "plan": "starter"},
    }
    raw = json.dumps(body).encode()
    sig = _sign(raw)
    res = client.post(
        "/api/webhooks/billing/mock",
        content=raw,
        headers={"X-Billing-Signature": sig},
    )
    assert res.status_code == 200
    db_session.expire_all()
    sub = (
        db_session.query(Subscription)
        .filter(Subscription.organization_id == org_id)
        .order_by(Subscription.created_at.desc())
        .first()
    )
    assert sub.status == "past_due"
    assert sub.grace_period_ends_at is not None
