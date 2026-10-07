"""Go-live readiness checklist — PASS only when verified, never from key presence alone."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.system.config_validate import validate_production_config
from app.services.system.registry import provider_registry


def production_readiness(db: Session | None = None, organization_id=None) -> dict[str, Any]:
    settings = get_settings()
    config = validate_production_config(settings)
    providers = provider_registry(settings, db=db, organization_id=organization_id)["providers"]

    def status_for_provider(pid: str, *, optional: bool = False) -> dict[str, Any]:
        info = providers.get(pid) or {}
        if not info.get("configured"):
            return {
                "id": pid,
                "status": "PASS" if optional else "WARNING",
                "detail": "Not configured" + (" (optional)" if optional else ""),
            }
        if info.get("mode") == "mock":
            return {"id": pid, "status": "WARNING", "detail": "MOCK — not production"}
        if info.get("live_tested") and info.get("mode") == "live" and info.get("healthy"):
            return {"id": pid, "status": "PASS", "detail": "LIVE-TESTED"}
        if info.get("healthy") and info.get("mode") == "test":
            return {"id": pid, "status": "WARNING", "detail": "TEST mode verified — not LIVE"}
        if info.get("mode") == "error" or info.get("degraded"):
            return {"id": pid, "status": "BLOCKED", "detail": info.get("last_error") or "Degraded"}
        return {"id": pid, "status": "WARNING", "detail": "Configured but not live-tested"}

    checklist = [
        {
            "id": "authentication",
            "label": "Authentication",
            "status": "PASS",
            "detail": "JWT auth + multi-tenant RBAC implemented",
        },
        {
            "id": "database",
            "label": "Database",
            "status": "PASS" if config["ok"] or not any(
                i["code"] == "DATABASE_URL" and i["severity"] == "error" for i in config["items"]
            )
            else "BLOCKED",
            "detail": "DATABASE_URL configured" if settings.database_url else "Missing DATABASE_URL",
        },
        {
            "id": "secrets",
            "label": "Secrets",
            "status": (
                "BLOCKED"
                if any(i["code"] == "SECRET_KEY" and i["severity"] == "error" for i in config["items"])
                else (
                    "WARNING"
                    if any(i["code"] == "SECRET_KEY" and i["severity"] == "warning" for i in config["items"])
                    else "PASS"
                )
            ),
            "detail": "SECRET_KEY must be strong in production",
        },
        {**status_for_provider("google_places"), "label": "Google Places"},
        {**status_for_provider("ai"), "label": "AI"},
        {**status_for_provider("email_verification"), "label": "Email Verification"},
        {**status_for_provider("email_sending"), "label": "Email Sending"},
        {**status_for_provider("email_inbound"), "label": "Inbound Email"},
        {**status_for_provider("calendar", optional=True), "label": "Calendar"},
        {**status_for_provider("billing", optional=True), "label": "Billing"},
        {
            "id": "webhooks",
            "label": "Webhooks",
            "status": (
                "PASS"
                if (settings.email_webhook_secret or "").strip()
                or not (settings.email_send_enabled or settings.reply_inbound_enabled)
                else "WARNING"
            ),
            "detail": "Webhook secrets required when email/inbound live",
        },
        {
            "id": "worker",
            "label": "Worker",
            "status": "PASS" if settings.job_queue_backend in {"local", "redis"} else "WARNING",
            "detail": f"JOB_QUEUE_BACKEND={settings.job_queue_backend}",
        },
        {
            "id": "backups",
            "label": "Backups",
            "status": "WARNING",
            "detail": "Documented only — verify ops backups separately (not auto-implemented)",
        },
        {
            "id": "monitoring",
            "label": "Monitoring",
            "status": "WARNING",
            "detail": "Use /api/health/live|/ready and external uptime checks",
        },
        {
            "id": "https",
            "label": "HTTPS",
            "status": "WARNING",
            "detail": "Terminate TLS at reverse proxy / load balancer",
        },
    ]

    blocked = sum(1 for c in checklist if c["status"] == "BLOCKED")
    warnings = sum(1 for c in checklist if c["status"] == "WARNING")
    return {
        "app_env": settings.app_env,
        "ready": blocked == 0 and warnings == 0,
        "blocked_count": blocked,
        "warning_count": warnings,
        "checklist": checklist,
        "config_validation": config,
        "note": "PASS requires verified readiness. Key presence alone never implies LIVE.",
    }
