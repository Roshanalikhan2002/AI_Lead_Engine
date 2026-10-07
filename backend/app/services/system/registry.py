"""Central provider registry — configuration status without claiming LIVE incorrectly."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.provider_health import ProviderHealthState

PROVIDER_IDS = (
    "google_places",
    "email_verification",
    "ai",
    "email_sending",
    "email_inbound",
    "calendar",
    "billing",
)

# Aliases accepted by test endpoint
PROVIDER_ALIASES = {
    "places": "google_places",
    "google": "google_places",
    "verification": "email_verification",
    "openai": "ai",
    "email": "email_sending",
    "sending": "email_sending",
    "reply": "email_inbound",
    "reply_inbound": "email_inbound",
    "inbound": "email_inbound",
    "stripe": "billing",
}


@dataclass
class ProviderConfigSnapshot:
    provider: str
    configured: bool
    enabled: bool
    # Intent from env — never "live" from keys alone
    config_mode: str  # unavailable | mock | test | disabled
    detail: dict[str, Any]


def normalize_provider_id(name: str) -> str | None:
    key = (name or "").strip().lower().replace("-", "_")
    if key in PROVIDER_IDS:
        return key
    return PROVIDER_ALIASES.get(key)


def _config_snapshot(settings: Settings) -> dict[str, ProviderConfigSnapshot]:
    places_mock = bool(settings.google_places_mock)
    places_key = bool((settings.google_places_api_key or "").strip())
    places_configured = places_mock or places_key

    ver_name = (settings.email_verification_provider or "").strip().lower()
    ver_configured = ver_name not in {"", "none", "unconfigured"}
    ver_mock = ver_name == "mock"

    ai_name = (settings.ai_provider or "").strip().lower()
    ai_configured = ai_name not in {"", "none", "unconfigured"}
    ai_mock = ai_name == "mock"
    ai_key = bool((settings.ai_api_key or "").strip())

    email_enabled = bool(settings.email_send_enabled)
    email_test = bool(settings.email_test_mode) or not email_enabled
    email_provider = (settings.email_sending_provider or "").strip().lower()
    sender_ok = bool((settings.sender_email or "").strip())
    email_configured = sender_ok or email_test or email_provider not in {"", "none"}
    if email_enabled and not email_test and not sender_ok:
        email_configured = False

    reply_enabled = bool(settings.reply_inbound_enabled)
    reply_secret = bool((settings.email_webhook_secret or "").strip())
    reply_configured = reply_enabled and reply_secret

    cal_name = (settings.calendar_provider or "").strip().lower()
    cal_configured = cal_name not in {"", "none", "unconfigured"}
    cal_mock = cal_name == "mock"

    bill_name = (settings.billing_provider or "unconfigured").strip().lower() or "unconfigured"
    if bill_name in {"", "none"}:
        bill_name = "unconfigured"
    bill_mock = bill_name == "mock"
    bill_stripe = bill_name == "stripe"
    bill_key = bool((settings.stripe_secret_key or "").strip())
    bill_configured = bill_name not in {"unconfigured"} and (not bill_stripe or bill_key)

    def mode_for(*, configured: bool, mock: bool, test: bool = False, enabled: bool = True) -> str:
        if not configured:
            return "unavailable"
        if mock:
            return "mock"
        if not enabled:
            return "disabled"
        if test:
            return "test"
        # Keys present ≠ LIVE — remain test until live-tested success
        return "test"

    return {
        "google_places": ProviderConfigSnapshot(
            provider="google_places",
            configured=places_configured,
            enabled=places_configured,
            config_mode=mode_for(configured=places_configured, mock=places_mock),
            detail={"mock": places_mock, "key_present": places_key},
        ),
        "email_verification": ProviderConfigSnapshot(
            provider="email_verification",
            configured=ver_configured,
            enabled=ver_configured,
            config_mode=mode_for(configured=ver_configured, mock=ver_mock),
            detail={"provider_name": ver_name or None, "mock": ver_mock},
        ),
        "ai": ProviderConfigSnapshot(
            provider="ai",
            configured=ai_configured,
            enabled=ai_configured,
            config_mode=mode_for(configured=ai_configured, mock=ai_mock),
            detail={
                "provider_name": ai_name or None,
                "mock": ai_mock,
                "key_present": ai_key,
                "model_configured": bool((settings.ai_model or "").strip()),
            },
        ),
        "email_sending": ProviderConfigSnapshot(
            provider="email_sending",
            configured=email_configured,
            enabled=email_enabled,
            config_mode=mode_for(
                configured=email_configured, mock=False, test=email_test, enabled=email_enabled
            ),
            detail={
                "send_enabled": email_enabled,
                "test_mode": email_test,
                "sender_configured": sender_ok,
                "test_recipient_configured": bool((settings.provider_test_email or "").strip()),
            },
        ),
        "email_inbound": ProviderConfigSnapshot(
            provider="email_inbound",
            configured=reply_configured or (reply_enabled and settings.email_test_mode),
            enabled=reply_enabled,
            config_mode=mode_for(
                configured=reply_enabled,
                mock=False,
                test=not reply_configured,
                enabled=reply_enabled,
            ),
            detail={"inbound_enabled": reply_enabled, "webhook_secret_configured": reply_secret},
        ),
        "calendar": ProviderConfigSnapshot(
            provider="calendar",
            configured=cal_configured,
            enabled=cal_configured,
            config_mode=mode_for(configured=cal_configured, mock=cal_mock),
            detail={"provider_name": cal_name or None, "mock": cal_mock, "calendar_live": False},
        ),
        "billing": ProviderConfigSnapshot(
            provider="billing",
            configured=bill_configured,
            enabled=bill_configured,
            config_mode=mode_for(
                configured=bill_configured,
                mock=bill_mock,
                test=bool(settings.billing_test_mode) or bill_mock,
            ),
            detail={
                "provider_name": bill_name,
                "billing_test_mode": bool(settings.billing_test_mode),
                "live_tested": False,
                "note": "Stripe is NOT LIVE-TESTED until a real provider operation succeeds.",
            },
        ),
    }


def _merge_health(
    snap: ProviderConfigSnapshot,
    health: ProviderHealthState | None,
) -> dict[str, Any]:
    """Merge config + DB health. Never claim live unless live_tested with success."""
    mode = snap.config_mode
    healthy = False
    live_tested = False
    degraded = False
    last_checked = None
    last_success = None
    last_failure = None
    last_error = None
    error_code = None

    if health:
        live_tested = bool(health.live_tested and health.last_success_at)
        degraded = bool(health.degraded) or (health.consecutive_failures or 0) >= 3
        last_checked = health.last_checked_at.isoformat() if health.last_checked_at else None
        last_success = health.last_success_at.isoformat() if health.last_success_at else None
        last_failure = health.last_failure_at.isoformat() if health.last_failure_at else None
        last_error = health.last_error_summary
        error_code = health.last_error_code
        if degraded and snap.configured:
            mode = "error"
            healthy = False
        elif live_tested and snap.config_mode not in {"mock", "unavailable", "disabled"}:
            # Billing Stripe sandbox → TEST forever (never claim LIVE from test-mode Stripe)
            if snap.provider == "billing" or snap.detail.get("billing_test_mode"):
                mode = "test"
                healthy = True
                live_tested = False
            # Email still gated by EMAIL_TEST_MODE / send disabled → TEST, not LIVE
            elif snap.provider == "email_sending" and snap.detail.get("test_mode"):
                mode = "test"
                healthy = True
                live_tested = False
            else:
                # Verified external success (Places / AI / verification / live send / etc.)
                mode = "live"
                healthy = True
        elif health.mode in {"mock", "test"} and health.last_success_at:
            mode = health.mode if health.mode in {"mock", "test"} else snap.config_mode
            healthy = mode in {"mock", "test"} and not degraded

    # Status label for UI
    if not snap.configured:
        status = "not_configured"
    elif mode == "mock":
        status = "test_mode"
    elif mode == "disabled":
        status = "disabled"
    elif mode == "error" or degraded:
        status = "degraded"
    elif mode == "live" and healthy:
        status = "healthy"
    elif mode == "test":
        status = "test_mode" if healthy or snap.configured else "configured"
    else:
        status = "configured" if snap.configured else "not_configured"

    out: dict[str, Any] = {
        "provider": snap.provider,
        "configured": snap.configured,
        "enabled": snap.enabled,
        "mode": mode,
        "status": status,
        "healthy": healthy,
        "live_tested": bool(live_tested and mode == "live"),
        "degraded": degraded,
        "last_checked": last_checked,
        "last_success": last_success,
        "last_error": last_error,
        "last_error_code": error_code,
        "last_failure": last_failure,
    }
    # Safe detail keys only
    safe_detail_keys = {
        "mock",
        "send_enabled",
        "test_mode",
        "sender_configured",
        "test_recipient_configured",
        "inbound_enabled",
        "webhook_secret_configured",
        "model_configured",
        "provider_name",
        "calendar_live",
        "billing_test_mode",
        "note",
    }
    for k, v in snap.detail.items():
        if k == "key_present":
            out["credentials_present"] = v
        elif k in safe_detail_keys:
            out[k] = v
    return out


def get_health_row(
    db: Session | None, provider: str, organization_id=None
) -> ProviderHealthState | None:
    if db is None:
        return None
    q = db.query(ProviderHealthState).filter(ProviderHealthState.provider == provider)
    if organization_id is None:
        q = q.filter(ProviderHealthState.organization_id.is_(None))
    else:
        q = q.filter(ProviderHealthState.organization_id == organization_id)
    return q.one_or_none()


def provider_registry(
    settings: Settings | None = None,
    db: Session | None = None,
    organization_id=None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    snaps = _config_snapshot(settings)
    providers = {}
    for pid, snap in snaps.items():
        health = get_health_row(db, pid, organization_id)
        # Prefer org-specific health; fall back to platform-level
        if health is None and organization_id is not None:
            health = get_health_row(db, pid, None)
        providers[pid] = _merge_health(snap, health)
    # Backward-compatible alias
    providers["reply_inbound"] = {**providers["email_inbound"], "provider": "reply_inbound"}
    return {"app_env": settings.app_env, "providers": providers}


def iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None
