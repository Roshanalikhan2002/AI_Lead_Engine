"""Billing provider abstraction — Unconfigured / Mock / Stripe."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from app.core.config import get_settings


@dataclass
class CheckoutSessionResult:
    provider: str
    mode: str  # live | test | mock | unavailable
    checkout_url: str | None
    session_id: str | None
    message: str


@dataclass
class PortalSessionResult:
    provider: str
    mode: str
    portal_url: str | None
    message: str


@dataclass
class SubscriptionResult:
    provider: str
    external_subscription_id: str | None
    external_customer_id: str | None
    plan: str
    status: str
    billing_interval: str
    current_period_start: datetime | None
    current_period_end: datetime | None
    cancel_at_period_end: bool = False
    trial_end: datetime | None = None
    raw: dict[str, Any] | None = None


class BillingProviderError(Exception):
    def __init__(self, message: str, *, code: str = "billing_error", status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class BillingProvider(Protocol):
    name: str

    def create_customer(self, *, organization_id: str, email: str, name: str) -> str: ...

    def create_checkout_session(
        self,
        *,
        customer_id: str | None,
        organization_id: str,
        plan: str,
        billing_interval: str,
        success_url: str,
        cancel_url: str,
    ) -> CheckoutSessionResult: ...

    def create_portal_session(
        self, *, customer_id: str, return_url: str
    ) -> PortalSessionResult: ...

    def create_subscription(
        self, *, customer_id: str, plan: str, billing_interval: str
    ) -> SubscriptionResult: ...

    def cancel_subscription(
        self, *, subscription_id: str, at_period_end: bool = True
    ) -> SubscriptionResult: ...

    def change_plan(
        self, *, subscription_id: str, plan: str, billing_interval: str
    ) -> SubscriptionResult: ...

    def resume_subscription(self, *, subscription_id: str) -> SubscriptionResult: ...

    def get_subscription(self, *, subscription_id: str) -> SubscriptionResult | None: ...

    def verify_webhook(self, payload: bytes, signature: str | None) -> dict[str, Any]: ...


class UnconfiguredBillingProvider:
    name = "unconfigured"

    def create_customer(self, *, organization_id: str, email: str, name: str) -> str:
        raise BillingProviderError(
            "Billing provider is not configured.",
            code="BILLING_NOT_CONFIGURED",
            status_code=503,
        )

    def create_checkout_session(self, **kwargs) -> CheckoutSessionResult:
        return CheckoutSessionResult(
            provider=self.name,
            mode="unavailable",
            checkout_url=None,
            session_id=None,
            message="Billing provider is not configured.",
        )

    def create_portal_session(self, **kwargs) -> PortalSessionResult:
        return PortalSessionResult(
            provider=self.name,
            mode="unavailable",
            portal_url=None,
            message="Billing provider is not configured.",
        )

    def create_subscription(self, **kwargs) -> SubscriptionResult:
        raise BillingProviderError(
            "Billing provider is not configured.",
            code="BILLING_NOT_CONFIGURED",
            status_code=503,
        )

    def cancel_subscription(self, **kwargs) -> SubscriptionResult:
        raise BillingProviderError(
            "Billing provider is not configured.",
            code="BILLING_NOT_CONFIGURED",
            status_code=503,
        )

    def change_plan(self, **kwargs) -> SubscriptionResult:
        raise BillingProviderError(
            "Billing provider is not configured.",
            code="BILLING_NOT_CONFIGURED",
            status_code=503,
        )

    def resume_subscription(self, **kwargs) -> SubscriptionResult:
        raise BillingProviderError(
            "Billing provider is not configured.",
            code="BILLING_NOT_CONFIGURED",
            status_code=503,
        )

    def get_subscription(self, **kwargs) -> SubscriptionResult | None:
        return None

    def verify_webhook(self, payload: bytes, signature: str | None) -> dict[str, Any]:
        raise BillingProviderError(
            "Billing provider is not configured.",
            code="BILLING_NOT_CONFIGURED",
            status_code=503,
        )


class MockBillingProvider:
    """Offline QA only — never claims real payment success."""

    name = "mock"
    _subs: dict[str, SubscriptionResult] = {}

    def create_customer(self, *, organization_id: str, email: str, name: str) -> str:
        return f"cus_mock_{organization_id[:8]}"

    def create_checkout_session(
        self,
        *,
        customer_id: str | None,
        organization_id: str,
        plan: str,
        billing_interval: str,
        success_url: str,
        cancel_url: str,
    ) -> CheckoutSessionResult:
        sid = f"cs_mock_{secrets.token_hex(8)}"
        return CheckoutSessionResult(
            provider=self.name,
            mode="mock",
            checkout_url=f"mock://checkout/{sid}?plan={plan}&interval={billing_interval}&org={organization_id}",
            session_id=sid,
            message="Mock checkout session (not a real payment URL).",
        )

    def create_portal_session(self, *, customer_id: str, return_url: str) -> PortalSessionResult:
        return PortalSessionResult(
            provider=self.name,
            mode="mock",
            portal_url=f"mock://portal/{customer_id}",
            message="Mock billing portal (not a real Stripe portal).",
        )

    def create_subscription(
        self, *, customer_id: str, plan: str, billing_interval: str
    ) -> SubscriptionResult:
        now = datetime.now(timezone.utc)
        end = now + (timedelta(days=365) if billing_interval == "year" else timedelta(days=30))
        sub_id = f"sub_mock_{secrets.token_hex(6)}"
        result = SubscriptionResult(
            provider=self.name,
            external_subscription_id=sub_id,
            external_customer_id=customer_id,
            plan=plan,
            status="active",
            billing_interval=billing_interval,
            current_period_start=now,
            current_period_end=end,
        )
        self._subs[sub_id] = result
        return result

    def cancel_subscription(
        self, *, subscription_id: str, at_period_end: bool = True
    ) -> SubscriptionResult:
        sub = self._subs.get(subscription_id)
        if not sub:
            raise BillingProviderError("Subscription not found", code="SUBSCRIPTION_NOT_FOUND", status_code=404)
        updated = SubscriptionResult(
            provider=self.name,
            external_subscription_id=sub.external_subscription_id,
            external_customer_id=sub.external_customer_id,
            plan=sub.plan,
            status="active" if at_period_end else "cancelled",
            billing_interval=sub.billing_interval,
            current_period_start=sub.current_period_start,
            current_period_end=sub.current_period_end,
            cancel_at_period_end=at_period_end,
            trial_end=sub.trial_end,
        )
        self._subs[subscription_id] = updated
        return updated

    def change_plan(
        self, *, subscription_id: str, plan: str, billing_interval: str
    ) -> SubscriptionResult:
        sub = self._subs.get(subscription_id)
        if not sub:
            # create synthetic for org already on mock
            return self.create_subscription(
                customer_id=f"cus_mock_{subscription_id[-8:]}",
                plan=plan,
                billing_interval=billing_interval,
            )
        updated = SubscriptionResult(
            provider=self.name,
            external_subscription_id=sub.external_subscription_id,
            external_customer_id=sub.external_customer_id,
            plan=plan,
            status="active",
            billing_interval=billing_interval,
            current_period_start=sub.current_period_start or datetime.now(timezone.utc),
            current_period_end=sub.current_period_end
            or datetime.now(timezone.utc) + timedelta(days=30),
            cancel_at_period_end=False,
        )
        self._subs[subscription_id] = updated
        return updated

    def resume_subscription(self, *, subscription_id: str) -> SubscriptionResult:
        sub = self._subs.get(subscription_id)
        if not sub:
            raise BillingProviderError("Subscription not found", code="SUBSCRIPTION_NOT_FOUND", status_code=404)
        updated = SubscriptionResult(
            provider=self.name,
            external_subscription_id=sub.external_subscription_id,
            external_customer_id=sub.external_customer_id,
            plan=sub.plan,
            status="active",
            billing_interval=sub.billing_interval,
            current_period_start=sub.current_period_start,
            current_period_end=sub.current_period_end,
            cancel_at_period_end=False,
        )
        self._subs[subscription_id] = updated
        return updated

    def get_subscription(self, *, subscription_id: str) -> SubscriptionResult | None:
        return self._subs.get(subscription_id)

    def verify_webhook(self, payload: bytes, signature: str | None) -> dict[str, Any]:
        settings = get_settings()
        secret = (settings.stripe_webhook_secret or "mock_webhook_secret").encode()
        expected = hmac.new(secret, payload, hashlib.sha256).hexdigest()
        if not signature or not hmac.compare_digest(expected, signature.replace("mock=", "")):
            # also accept signature == expected for tests
            if signature != expected and signature != f"mock={expected}":
                raise BillingProviderError("Invalid webhook signature", code="INVALID_SIGNATURE", status_code=401)
        import json

        return json.loads(payload.decode("utf-8"))


class StripeBillingProvider:
    """Real Stripe — only when BILLING_PROVIDER=stripe and keys configured."""

    name = "stripe"

    def __init__(self) -> None:
        settings = get_settings()
        if not (settings.stripe_secret_key or "").strip():
            raise BillingProviderError(
                "STRIPE_SECRET_KEY is not configured.",
                code="BILLING_NOT_CONFIGURED",
                status_code=503,
            )
        self._secret = settings.stripe_secret_key.strip()
        self._webhook_secret = (settings.stripe_webhook_secret or "").strip()

    def create_customer(self, *, organization_id: str, email: str, name: str) -> str:
        raise BillingProviderError(
            "Stripe live API is not executed in this environment. Configure and LIVE-TEST separately.",
            code="STRIPE_NOT_LIVE_TESTED",
            status_code=501,
        )

    def create_checkout_session(self, **kwargs) -> CheckoutSessionResult:
        raise BillingProviderError(
            "Stripe checkout requires a live-tested Stripe integration.",
            code="STRIPE_NOT_LIVE_TESTED",
            status_code=501,
        )

    def create_portal_session(self, **kwargs) -> PortalSessionResult:
        raise BillingProviderError(
            "Stripe portal requires a live-tested Stripe integration.",
            code="STRIPE_NOT_LIVE_TESTED",
            status_code=501,
        )

    def create_subscription(self, **kwargs) -> SubscriptionResult:
        raise BillingProviderError(
            "Stripe subscription requires a live-tested Stripe integration.",
            code="STRIPE_NOT_LIVE_TESTED",
            status_code=501,
        )

    def cancel_subscription(self, **kwargs) -> SubscriptionResult:
        raise BillingProviderError(
            "Stripe cancellation requires a live-tested Stripe integration.",
            code="STRIPE_NOT_LIVE_TESTED",
            status_code=501,
        )

    def change_plan(self, **kwargs) -> SubscriptionResult:
        raise BillingProviderError(
            "Stripe plan change requires a live-tested Stripe integration.",
            code="STRIPE_NOT_LIVE_TESTED",
            status_code=501,
        )

    def resume_subscription(self, **kwargs) -> SubscriptionResult:
        raise BillingProviderError(
            "Stripe resume requires a live-tested Stripe integration.",
            code="STRIPE_NOT_LIVE_TESTED",
            status_code=501,
        )

    def get_subscription(self, **kwargs) -> SubscriptionResult | None:
        return None

    def verify_webhook(self, payload: bytes, signature: str | None) -> dict[str, Any]:
        if not self._webhook_secret:
            raise BillingProviderError(
                "STRIPE_WEBHOOK_SECRET is not configured.",
                code="BILLING_NOT_CONFIGURED",
                status_code=503,
            )
        # Signature verification without calling Stripe SDK — HMAC of payload
        expected = hmac.new(
            self._webhook_secret.encode(), payload, hashlib.sha256
        ).hexdigest()
        if not signature or expected not in signature:
            raise BillingProviderError("Invalid webhook signature", code="INVALID_SIGNATURE", status_code=401)
        import json

        return json.loads(payload.decode("utf-8"))


def get_billing_provider():
    settings = get_settings()
    name = (settings.billing_provider or "unconfigured").strip().lower()
    if settings.is_production() and name == "mock":
        raise BillingProviderError(
            "Mock billing cannot be used in production.",
            code="INVALID_BILLING_CONFIG",
            status_code=500,
        )
    if name in {"", "none", "unconfigured"}:
        return UnconfiguredBillingProvider()
    if name == "mock":
        return MockBillingProvider()
    if name == "stripe":
        return StripeBillingProvider()
    return UnconfiguredBillingProvider()
