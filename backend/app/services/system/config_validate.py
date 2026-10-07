"""Structured production configuration validation — never returns secrets."""

from __future__ import annotations

from typing import Any, Literal

from app.core.config import Settings, get_settings

Severity = Literal["pass", "warning", "error"]


def _item(code: str, severity: Severity, message: str, *, category: str = "config") -> dict[str, Any]:
    return {"code": code, "severity": severity, "message": message, "category": category}


def validate_production_config(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    env = (settings.app_env or "development").strip().lower()
    items: list[dict[str, Any]] = []

    # Core
    if not (settings.database_url or "").strip():
        items.append(_item("DATABASE_URL", "error", "DATABASE_URL is required", category="database"))
    else:
        items.append(_item("DATABASE_URL", "pass", "Database URL is set", category="database"))

    secret = (settings.secret_key or "").strip()
    if env == "production":
        if (
            not secret
            or secret in {"changeme", "secret", "leadflow-dev-only-secret-change-me"}
            or len(secret) < 32
        ):
            items.append(
                _item("SECRET_KEY", "error", "SECRET_KEY must be a strong 32+ character value", category="secrets")
            )
        else:
            items.append(_item("SECRET_KEY", "pass", "SECRET_KEY is set", category="secrets"))
    else:
        if not secret:
            items.append(_item("SECRET_KEY", "warning", "SECRET_KEY empty (ok for local only)", category="secrets"))
        else:
            items.append(_item("SECRET_KEY", "pass", "SECRET_KEY is set", category="secrets"))

    if env not in {"development", "test", "production"}:
        items.append(_item("APP_ENV", "error", f"Invalid APP_ENV={env}", category="environment"))
    else:
        items.append(_item("APP_ENV", "pass", f"APP_ENV={env}", category="environment"))

    cors = settings.cors_origin_list()
    if env == "production" and any("localhost" in o for o in cors) and not (settings.cors_origins or "").strip():
        items.append(
            _item(
                "CORS",
                "warning",
                "CORS includes localhost defaults — set CORS_ORIGINS for production domains",
                category="network",
            )
        )
    else:
        items.append(_item("CORS", "pass", "CORS origins configured", category="network"))

    # Mock safety in production
    if env == "production":
        if settings.google_places_mock:
            items.append(_item("GOOGLE_PLACES_MOCK", "error", "Mock Places not allowed in production", category="providers"))
        if (settings.ai_provider or "").strip().lower() == "mock":
            items.append(_item("AI_PROVIDER", "error", "AI_PROVIDER=mock not allowed in production", category="providers"))
        if (settings.email_verification_provider or "").strip().lower() == "mock":
            items.append(
                _item(
                    "EMAIL_VERIFICATION_PROVIDER",
                    "error",
                    "Mock email verification not allowed in production",
                    category="providers",
                )
            )
        if (settings.calendar_provider or "").strip().lower() == "mock":
            items.append(_item("CALENDAR_PROVIDER", "error", "Mock calendar not allowed in production", category="providers"))
        if (settings.billing_provider or "").strip().lower() == "mock":
            items.append(_item("BILLING_PROVIDER", "error", "Mock billing not allowed in production", category="providers"))
        if settings.email_send_enabled and settings.email_test_mode:
            items.append(
                _item(
                    "EMAIL_MODE",
                    "error",
                    "EMAIL_SEND_ENABLED=true with EMAIL_TEST_MODE=true is inconsistent for live sends",
                    category="email",
                )
            )
        if settings.email_send_enabled and not (settings.sender_email or "").strip():
            items.append(_item("SENDER_EMAIL", "error", "SENDER_EMAIL required when sending enabled", category="email"))
        if settings.email_send_enabled and not (settings.email_webhook_secret or "").strip():
            items.append(
                _item("EMAIL_WEBHOOK_SECRET", "error", "EMAIL_WEBHOOK_SECRET required when sending enabled", category="webhooks")
            )
        if settings.reply_inbound_enabled and not (settings.email_webhook_secret or "").strip():
            items.append(
                _item("INBOUND_WEBHOOK", "error", "Webhook secret required when inbound enabled", category="webhooks")
            )
        if (settings.billing_provider or "").strip().lower() == "stripe" and not (
            settings.stripe_secret_key or ""
        ).strip():
            items.append(_item("STRIPE_SECRET_KEY", "error", "Stripe selected but key missing", category="billing"))

    # Optional providers — warnings only
    if not (settings.google_places_api_key or "").strip() and not settings.google_places_mock:
        items.append(
            _item("GOOGLE_PLACES", "warning", "Google Places not configured (optional until go-live)", category="providers")
        )
    else:
        items.append(_item("GOOGLE_PLACES", "pass", "Google Places configured or mock", category="providers"))

    ai = (settings.ai_provider or "").strip().lower()
    if ai in {"", "none", "unconfigured"}:
        items.append(_item("AI", "warning", "AI provider not configured", category="providers"))
    else:
        items.append(_item("AI", "pass", f"AI provider={ai}", category="providers"))

    if not settings.email_send_enabled:
        items.append(_item("EMAIL_SENDING", "pass", "Email sending disabled (safe default)", category="email"))
    elif settings.email_test_mode:
        items.append(_item("EMAIL_SENDING", "warning", "Email sending in TEST MODE", category="email"))
    else:
        if not (settings.provider_test_email or "").strip():
            items.append(
                _item(
                    "PROVIDER_TEST_EMAIL",
                    "warning",
                    "PROVIDER_TEST_EMAIL not set — required before live provider email tests",
                    category="email",
                )
            )
        items.append(_item("EMAIL_SENDING", "warning", "Email sending LIVE flags enabled — verify carefully", category="email"))

    bill = (settings.billing_provider or "unconfigured").strip().lower()
    if bill in {"", "unconfigured", "none"}:
        items.append(_item("BILLING", "pass", "Billing unconfigured — Free plan OK", category="billing"))
    elif bill == "mock":
        sev: Severity = "error" if env == "production" else "warning"
        items.append(_item("BILLING", sev, "Billing provider is mock", category="billing"))
    else:
        items.append(_item("BILLING", "warning", f"Billing provider={bill} — not LIVE until verified", category="billing"))

    cal = (settings.calendar_provider or "").strip().lower()
    if cal in {"", "none", "unconfigured"}:
        items.append(_item("CALENDAR", "pass", "Calendar unavailable (optional)", category="providers"))
    else:
        items.append(_item("CALENDAR", "warning", f"Calendar={cal} — not LIVE until verified", category="providers"))

    errors = sum(1 for i in items if i["severity"] == "error")
    warnings = sum(1 for i in items if i["severity"] == "warning")
    return {
        "app_env": env,
        "ok": errors == 0,
        "error_count": errors,
        "warning_count": warnings,
        "items": items,
    }
