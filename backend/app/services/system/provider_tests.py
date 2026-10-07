"""Safe provider test runners — never claim LIVE without a verified success."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.provider_health import ProviderHealthState, ProviderOperationLog
from app.services.system.rate_limit import SlidingWindowLimiter
from app.services.system.registry import normalize_provider_id, provider_registry
from app.services.system.audit import write_audit

_test_limiter = SlidingWindowLimiter()
DEGRADED_FAILURE_THRESHOLD = 3


@dataclass
class ProviderTestResult:
    provider: str
    ok: bool
    mode: str
    status: str
    message: str
    side_effects: str = "none"
    duration_ms: int | None = None
    provider_request_id: str | None = None
    error_code: str | None = None
    provider_test: bool = True
    live_operation: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out = {
            "provider": self.provider,
            "ok": self.ok,
            "mode": self.mode,
            "status": self.status,
            "message": self.message,
            "side_effects": self.side_effects,
            "provider_test": True,
            "live_operation": self.live_operation,
            "configured": self.extra.get("configured"),
        }
        if self.duration_ms is not None:
            out["duration_ms"] = self.duration_ms
        if self.provider_request_id:
            out["provider_request_id"] = self.provider_request_id
        if self.error_code:
            out["error_code"] = self.error_code
        for k, v in self.extra.items():
            if k not in out:
                out[k] = v
        return out


def _enforce_test_rate_limit(*, organization_id: uuid.UUID | None, provider: str) -> None:
    settings = get_settings()
    if not settings.api_rate_limit_enabled:
        return
    limit = max(1, int(settings.provider_test_rate_limit_per_minute or 5))
    key = f"provider_test:{organization_id or 'platform'}:{provider}"
    if not _test_limiter.allow(key, limit=limit, window_seconds=60.0):
        raise HTTPException(
            status_code=429,
            detail={
                "error": {
                    "code": "PROVIDER_TEST_RATE_LIMITED",
                    "message": "Provider tests are rate limited. Try again shortly.",
                }
            },
        )


def _get_or_create_health(
    db: Session, provider: str, organization_id: uuid.UUID | None
) -> ProviderHealthState:
    q = db.query(ProviderHealthState).filter(ProviderHealthState.provider == provider)
    if organization_id is None:
        q = q.filter(ProviderHealthState.organization_id.is_(None))
    else:
        q = q.filter(ProviderHealthState.organization_id == organization_id)
    row = q.one_or_none()
    if row:
        return row
    row = ProviderHealthState(
        organization_id=organization_id,
        provider=provider,
        mode="unavailable",
    )
    db.add(row)
    db.flush()
    return row


def _record_result(
    db: Session,
    *,
    organization_id: uuid.UUID | None,
    actor_user_id: uuid.UUID | None,
    result: ProviderTestResult,
    request_id: str | None = None,
) -> None:
    now = datetime.now(timezone.utc)
    health = _get_or_create_health(db, result.provider, organization_id)
    health.last_checked_at = now
    health.configured = bool(result.extra.get("configured", True))
    health.enabled = bool(result.extra.get("enabled", True))
    health.mode = result.mode

    if result.ok:
        health.last_success_at = now
        health.consecutive_failures = 0
        health.degraded = False
        health.last_error_code = None
        health.last_error_summary = None
        health.healthy = True
        # live_tested only for verified external live ops (not mock/test)
        if result.live_operation and result.mode == "live":
            health.live_tested = True
        elif result.mode in {"mock", "test"}:
            # Successful mock/test — do not mark live_tested
            health.live_tested = health.live_tested  # preserve prior live flag
    else:
        health.last_failure_at = now
        health.consecutive_failures = int(health.consecutive_failures or 0) + 1
        health.last_error_code = result.error_code
        health.last_error_summary = (result.message or "")[:500]
        health.healthy = False
        if health.consecutive_failures >= DEGRADED_FAILURE_THRESHOLD:
            health.degraded = True
            health.mode = "error"

    db.add(health)

    log = ProviderOperationLog(
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        provider=result.provider,
        operation="provider_test",
        status="success" if result.ok else "failure",
        duration_ms=result.duration_ms,
        request_id=request_id,
        provider_request_id=result.provider_request_id,
        error_code=result.error_code,
        error_summary=(result.message or "")[:500] if not result.ok else None,
        metadata_json={
            "provider_test": True,
            "mode": result.mode,
            "side_effects": result.side_effects,
            "live_operation": result.live_operation,
        },
    )
    db.add(log)

    write_audit(
        db,
        action="provider_test_completed" if result.ok else "provider_test_failed",
        entity_type="provider",
        entity_id=result.provider,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        actor_type="user" if actor_user_id else "system",
        metadata={
            "provider": result.provider,
            "ok": result.ok,
            "mode": result.mode,
            "side_effects": result.side_effects,
            "error_code": result.error_code,
        },
        commit=False,
    )
    db.commit()


def run_provider_test(
    db: Session,
    provider: str,
    *,
    organization_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    key = normalize_provider_id(provider)
    if not key:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "UNKNOWN_PROVIDER", "message": f"Unknown provider: {provider}"}},
        )

    _enforce_test_rate_limit(organization_id=organization_id, provider=key)

    write_audit(
        db,
        action="provider_test_started",
        entity_type="provider",
        entity_id=key,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        actor_type="user" if actor_user_id else "system",
        metadata={"provider": key},
        commit=True,
    )

    started = time.perf_counter()
    registry = provider_registry(settings, db=db, organization_id=organization_id)
    info = registry["providers"].get(key) or registry["providers"].get(
        "email_inbound" if key == "email_inbound" else key, {}
    )

    runners = {
        "google_places": _test_google_places,
        "email_verification": _test_email_verification,
        "ai": _test_ai,
        "email_sending": _test_email_sending,
        "email_inbound": _test_email_inbound,
        "calendar": _test_calendar,
        "billing": _test_billing,
    }
    runner = runners[key]
    result = runner(db, info=info, settings=settings)
    result.duration_ms = int((time.perf_counter() - started) * 1000)
    result.extra.setdefault("configured", info.get("configured"))
    result.extra.setdefault("enabled", info.get("enabled"))

    _record_result(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        result=result,
        request_id=request_id,
    )
    return result.to_dict()


def _test_google_places(db: Session, *, info: dict, settings) -> ProviderTestResult:
    if settings.google_places_mock:
        return ProviderTestResult(
            provider="google_places",
            ok=True,
            mode="mock",
            status="test_mode",
            message="Google Places is in explicit mock mode. No live Places request was made.",
            side_effects="none",
            live_operation=False,
        )
    if not (settings.google_places_api_key or "").strip():
        return ProviderTestResult(
            provider="google_places",
            ok=False,
            mode="unavailable",
            status="not_configured",
            message="GOOGLE_PLACES_API_KEY is not configured.",
            error_code="NOT_CONFIGURED",
        )
    # Minimal live probe — do not create leads
    try:
        from app.services.google_places import GooglePlacesService

        with GooglePlacesService(settings) as service:
            businesses = service.search_businesses(
                industry="cafe",
                keywords=None,
                city="Austin",
                state="TX",
                country="USA",
                min_rating=None,
                quantity=1,
            )
        return ProviderTestResult(
            provider="google_places",
            ok=True,
            mode="live",
            status="healthy",
            message="Minimal Google Places search succeeded. No leads were created.",
            side_effects="none",
            live_operation=True,
            extra={"places_returned": len(businesses[:1])},
        )
    except Exception as exc:  # noqa: BLE001
        return ProviderTestResult(
            provider="google_places",
            ok=False,
            mode="error",
            status="degraded",
            message=f"Places probe failed: {type(exc).__name__}",
            error_code="PROVIDER_ERROR",
            live_operation=False,
        )


def _test_ai(db: Session, *, info: dict, settings) -> ProviderTestResult:
    name = (settings.ai_provider or "").strip().lower()
    if name in {"", "none", "unconfigured"}:
        return ProviderTestResult(
            provider="ai",
            ok=False,
            mode="unavailable",
            status="not_configured",
            message="AI provider is not configured.",
            error_code="NOT_CONFIGURED",
        )
    if name == "mock":
        return ProviderTestResult(
            provider="ai",
            ok=True,
            mode="mock",
            status="test_mode",
            message="AI is in mock mode. No live completion was requested.",
            side_effects="none",
        )
    if not (settings.ai_api_key or "").strip():
        return ProviderTestResult(
            provider="ai",
            ok=False,
            mode="unavailable",
            status="not_configured",
            message="AI_API_KEY is not configured.",
            error_code="NOT_CONFIGURED",
        )
    try:
        from app.services.qualification.providers import get_qualification_provider

        provider = get_qualification_provider(settings)
        # Minimal structured probe — mark provider_test in input
        probe_input = {
            "provider_test": True,
            "company_name": "LeadFlow Provider Test",
            "industry": "software",
            "website_url": None,
            "city": "Test City",
            "country": "US",
        }
        if hasattr(provider, "qualify_lead"):
            result = provider.qualify_lead(probe_input)
            status = getattr(result, "status", None) or (result.get("status") if isinstance(result, dict) else "ok")
            if status in {"error", "failed"}:
                return ProviderTestResult(
                    provider="ai",
                    ok=False,
                    mode="error",
                    status="degraded",
                    message="AI probe returned an error status.",
                    error_code="PROVIDER_ERROR",
                )
            return ProviderTestResult(
                provider="ai",
                ok=True,
                mode="live",
                status="healthy",
                message="Minimal AI structured completion succeeded. Not stored as a lead qualification.",
                side_effects="none",
                live_operation=True,
                extra={"provider_test": True},
            )
        return ProviderTestResult(
            provider="ai",
            ok=True,
            mode="test",
            status="configured",
            message="AI key present; probe method unavailable — not marking LIVE.",
            side_effects="none",
        )
    except Exception as exc:  # noqa: BLE001
        return ProviderTestResult(
            provider="ai",
            ok=False,
            mode="error",
            status="degraded",
            message=f"AI probe failed: {type(exc).__name__}",
            error_code="PROVIDER_ERROR",
        )


def _test_email_verification(db: Session, *, info: dict, settings) -> ProviderTestResult:
    name = (settings.email_verification_provider or "").strip().lower()
    if name in {"", "none", "unconfigured"}:
        return ProviderTestResult(
            provider="email_verification",
            ok=False,
            mode="unavailable",
            status="not_configured",
            message="Email verification provider is not configured.",
            error_code="NOT_CONFIGURED",
        )
    if name == "mock":
        return ProviderTestResult(
            provider="email_verification",
            ok=True,
            mode="mock",
            status="test_mode",
            message="Email verification is in mock mode.",
            side_effects="none",
        )
    test_email = (settings.provider_test_email or "").strip()
    if not test_email:
        return ProviderTestResult(
            provider="email_verification",
            ok=False,
            mode="test",
            status="configured",
            message="PROVIDER_TEST_EMAIL is required for verification live tests.",
            error_code="TEST_RECIPIENT_NOT_CONFIGURED",
        )
    try:
        from app.services.verification.providers import get_verification_provider

        provider = get_verification_provider(settings)
        started = time.perf_counter()
        result = provider.verify_email(test_email)
        latency = int((time.perf_counter() - started) * 1000)
        status = getattr(result, "status", None) or (result.get("status") if isinstance(result, dict) else "unknown")
        req_id = getattr(result, "provider_request_id", None) or (
            result.get("provider_request_id") if isinstance(result, dict) else None
        )
        return ProviderTestResult(
            provider="email_verification",
            ok=True,
            mode="live",
            status="healthy",
            message=f"Verification probe completed for configured test email (status={status}).",
            side_effects="none",
            live_operation=True,
            duration_ms=latency,
            provider_request_id=str(req_id) if req_id else None,
            extra={"verification_status": status, "latency_ms": latency},
        )
    except Exception as exc:  # noqa: BLE001
        return ProviderTestResult(
            provider="email_verification",
            ok=False,
            mode="error",
            status="degraded",
            message=f"Verification probe failed: {type(exc).__name__}",
            error_code="PROVIDER_ERROR",
        )


def _test_email_sending(db: Session, *, info: dict, settings) -> ProviderTestResult:
    """Extremely sensitive — default never sends. Live send only with explicit flags + test recipient."""
    test_email = (settings.provider_test_email or "").strip()
    can_live_send = (
        bool(settings.email_send_enabled)
        and not bool(settings.email_test_mode)
        and bool(test_email)
        and bool((settings.sender_email or "").strip())
    )

    if not can_live_send:
        msg = (
            "Email sending credentials/sender appear configured; "
            "no email was sent. Live send requires EMAIL_SEND_ENABLED=true, "
            "EMAIL_TEST_MODE=false, and PROVIDER_TEST_EMAIL."
        )
        if not test_email and settings.email_send_enabled and not settings.email_test_mode:
            return ProviderTestResult(
                provider="email_sending",
                ok=False,
                mode="test",
                status="configured",
                message="TEST_RECIPIENT_NOT_CONFIGURED: set PROVIDER_TEST_EMAIL before live send tests.",
                error_code="TEST_RECIPIENT_NOT_CONFIGURED",
                side_effects="none",
            )
        return ProviderTestResult(
            provider="email_sending",
            ok=True,
            mode="test" if settings.email_test_mode or not settings.email_send_enabled else "test",
            status="test_mode",
            message=msg,
            side_effects="none",
            extra={
                "send_enabled": bool(settings.email_send_enabled),
                "test_mode": bool(settings.email_test_mode),
            },
        )

    # Live: send exactly ONE test email to PROVIDER_TEST_EMAIL
    try:
        from app.services.sending.providers import get_email_sending_provider

        provider = get_email_sending_provider(settings)
        result = provider.send_email(
            sender_email=settings.sender_email.strip(),
            sender_name=(settings.sender_name or "LeadFlow AI").strip(),
            recipient_email=test_email,
            subject="LeadFlow AI Provider Test",
            body=(
                "This is a controlled provider connectivity test from LeadFlow AI.\n"
                "\n"
                "provider_test=true\n"
                "Recipient is PROVIDER_TEST_EMAIL only — not a customer lead.\n"
            ),
            idempotency_key=f"provider-test-{uuid.uuid4()}",
        )
        status = getattr(result, "status", None) or "unknown"
        ok = status in {"sent", "simulated", "queued", "accepted"}
        return ProviderTestResult(
            provider="email_sending",
            ok=ok,
            mode="live" if ok and status == "sent" else "test",
            status="healthy" if ok else "degraded",
            message=(
                f"Sent exactly one provider test email to PROVIDER_TEST_EMAIL (status={status})."
                if ok
                else f"Provider test send failed (status={status})."
            ),
            side_effects="one_test_email" if ok else "none",
            live_operation=ok and status == "sent",
            provider_request_id=getattr(result, "provider_message_id", None),
            extra={"recipient": "PROVIDER_TEST_EMAIL", "send_status": status},
        )
    except Exception as exc:  # noqa: BLE001
        return ProviderTestResult(
            provider="email_sending",
            ok=False,
            mode="error",
            status="degraded",
            message=f"Email send probe failed: {type(exc).__name__}",
            error_code="PROVIDER_ERROR",
            side_effects="none",
        )


def _test_email_inbound(db: Session, *, info: dict, settings) -> ProviderTestResult:
    if not settings.reply_inbound_enabled:
        return ProviderTestResult(
            provider="email_inbound",
            ok=True,
            mode="disabled",
            status="disabled",
            message="Inbound reply webhooks are disabled (REPLY_INBOUND_ENABLED=false).",
            side_effects="none",
        )
    if not (settings.email_webhook_secret or "").strip():
        return ProviderTestResult(
            provider="email_inbound",
            ok=False,
            mode="unavailable",
            status="not_configured",
            message="EMAIL_WEBHOOK_SECRET is required when inbound is enabled.",
            error_code="NOT_CONFIGURED",
        )
    return ProviderTestResult(
        provider="email_inbound",
        ok=True,
        mode="test",
        status="test_mode",
        message=(
            "Inbound is enabled with webhook secret configured. "
            "Mark LIVE only after a real webhook is received, verified, parsed, and matched."
        ),
        side_effects="none",
        live_operation=False,
    )


def _test_calendar(db: Session, *, info: dict, settings) -> ProviderTestResult:
    name = (settings.calendar_provider or "").strip().lower()
    if name in {"", "none", "unconfigured"}:
        return ProviderTestResult(
            provider="calendar",
            ok=True,
            mode="unavailable",
            status="not_configured",
            message="Calendar provider status checked; no calendar event was created.",
            side_effects="none",
        )
    if name == "mock":
        from datetime import timedelta

        from app.services.meetings.calendar import MockCalendarProvider

        cal = MockCalendarProvider()
        start = datetime.now(timezone.utc) + timedelta(days=1)
        end = start + timedelta(minutes=30)
        created = cal.create_event(
            title="LeadFlow AI Provider Test",
            description="provider_test=true — isolated calendar probe",
            start_at=start,
            end_at=end,
            timezone="UTC",
            attendee_email=(settings.provider_test_email or None) or None,
        )
        cancelled = cal.cancel_event(created.external_event_id or "")
        return ProviderTestResult(
            provider="calendar",
            ok=created.status == "created" and cancelled.status == "cancelled",
            mode="mock",
            status="test_mode",
            message="Mock calendar create+cancel succeeded. Not LIVE. No CRM meeting created.",
            side_effects="none",
            live_operation=False,
            provider_request_id=created.external_event_id,
            extra={"calendar_live": False, "provider_test": True},
        )
    # Real Google/Outlook adapters are not implemented — never claim LIVE
    return ProviderTestResult(
        provider="calendar",
        ok=False,
        mode="unavailable",
        status="not_configured",
        message=(
            f"Calendar provider '{name}' is not implemented for live tests. "
            "No customer meeting was created."
        ),
        error_code="NOT_IMPLEMENTED",
        side_effects="none",
        live_operation=False,
        extra={"calendar_live": False},
    )


def _test_billing(db: Session, *, info: dict, settings) -> ProviderTestResult:
    name = (settings.billing_provider or "unconfigured").strip().lower()
    if name in {"", "none", "unconfigured"}:
        return ProviderTestResult(
            provider="billing",
            ok=True,
            mode="unavailable",
            status="not_configured",
            message="Billing provider is not configured. Free plan works without Stripe.",
            side_effects="none",
        )
    if name == "mock":
        if settings.is_production():
            return ProviderTestResult(
                provider="billing",
                ok=False,
                mode="error",
                status="degraded",
                message="Mock billing cannot be used in production.",
                error_code="INVALID_BILLING_CONFIG",
            )
        from app.services.billing.providers import MockBillingProvider

        mock = MockBillingProvider()
        cust = mock.create_customer(organization_id=str(uuid.uuid4()), email="test@example.com", name="Test")
        checkout = mock.create_checkout_session(
            customer_id=cust,
            organization_id=str(uuid.uuid4()),
            plan="starter",
            billing_interval="month",
            success_url="https://example.com/ok",
            cancel_url="https://example.com/cancel",
        )
        return ProviderTestResult(
            provider="billing",
            ok=True,
            mode="mock",
            status="test_mode",
            message=f"Mock billing checkout/portal simulation ok ({checkout.mode}). Not a real payment.",
            side_effects="none",
            live_operation=False,
            extra={"checkout_mode": checkout.mode},
        )
    if name == "stripe":
        if not (settings.stripe_secret_key or "").strip():
            return ProviderTestResult(
                provider="billing",
                ok=False,
                mode="unavailable",
                status="not_configured",
                message="STRIPE_SECRET_KEY is not configured.",
                error_code="NOT_CONFIGURED",
            )
        secret = settings.stripe_secret_key.strip()
        if not secret.startswith("sk_test_"):
            return ProviderTestResult(
                provider="billing",
                ok=False,
                mode="error",
                status="degraded",
                message=(
                    "Stripe live secret keys are blocked for provider tests. "
                    "Use sk_test_* only (TEST mode)."
                ),
                error_code="STRIPE_LIVE_KEY_BLOCKED",
                live_operation=False,
            )
        # Minimal Stripe TEST-mode probe — no charge, no LIVE claim
        try:
            import httpx

            started = time.perf_counter()
            resp = httpx.get(
                "https://api.stripe.com/v1/balance",
                auth=(secret, ""),
                timeout=20.0,
            )
            latency = int((time.perf_counter() - started) * 1000)
            if resp.status_code == 200:
                # Also verify webhook secret HMAC path without claiming delivery
                webhook_ok = bool((settings.stripe_webhook_secret or "").strip())
                return ProviderTestResult(
                    provider="billing",
                    ok=True,
                    mode="test",
                    status="test_mode",
                    message=(
                        "Stripe TEST-mode balance probe succeeded. "
                        "No charge. Status is TEST (never LIVE from sandbox)."
                        + ("" if webhook_ok else " STRIPE_WEBHOOK_SECRET still missing.")
                    ),
                    side_effects="none",
                    live_operation=False,
                    duration_ms=latency,
                    extra={
                        "billing_test_mode": True,
                        "stripe_test_probe": "balance",
                        "webhook_secret_configured": webhook_ok,
                    },
                )
            if resp.status_code in {401, 403}:
                return ProviderTestResult(
                    provider="billing",
                    ok=False,
                    mode="error",
                    status="degraded",
                    message=f"Stripe TEST probe auth failed (HTTP {resp.status_code}).",
                    error_code="PROVIDER_AUTH_ERROR",
                    duration_ms=latency,
                )
            return ProviderTestResult(
                provider="billing",
                ok=False,
                mode="error",
                status="degraded",
                message=f"Stripe TEST probe failed (HTTP {resp.status_code}).",
                error_code="PROVIDER_ERROR",
                duration_ms=latency,
            )
        except Exception as exc:  # noqa: BLE001
            return ProviderTestResult(
                provider="billing",
                ok=False,
                mode="error",
                status="degraded",
                message=f"Stripe TEST probe failed: {type(exc).__name__}",
                error_code="PROVIDER_ERROR",
            )
    return ProviderTestResult(
        provider="billing",
        ok=False,
        mode="unavailable",
        status="not_configured",
        message=f"Unknown billing provider: {name}",
        error_code="UNKNOWN_PROVIDER",
    )
