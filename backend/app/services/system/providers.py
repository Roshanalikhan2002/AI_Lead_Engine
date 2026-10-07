"""Safe provider status for ops / frontend — never exposes secrets."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings, validate_settings
from app.services.system.registry import provider_registry


def provider_statuses(
    settings: Settings | None = None,
    db: Session | None = None,
    organization_id=None,
) -> dict:
    """Backward-compatible provider status. LIVE only after verified success."""
    return provider_registry(settings=settings, db=db, organization_id=organization_id)


def system_health(db: Session | None = None, settings: Settings | None = None, organization_id=None) -> dict:
    settings = settings or get_settings()
    providers = provider_statuses(settings, db=db, organization_id=organization_id)
    config_problems = validate_settings(settings)

    db_status = "unavailable"
    db_detail = "not_checked"
    if db is not None:
        try:
            db.execute(text("SELECT 1"))
            db_status = "healthy"
            db_detail = "ok"
        except Exception as exc:  # noqa: BLE001
            db_status = "unavailable"
            db_detail = type(exc).__name__

    return {
        "status": "ok" if db_status == "healthy" and not (settings.is_production() and config_problems) else "degraded",
        "app_env": settings.app_env,
        "database": {"status": db_status, "detail": db_detail},
        "config_problems": config_problems if not settings.is_production() else [],
        "config_ok": len(config_problems) == 0,
        "authentication": {
            "status": "implemented",
            "note": "JWT access + refresh sessions with organization membership. Protect public exposure with HTTPS and strong SECRET_KEY.",
        },
        "job_queue": {
            "backend": settings.job_queue_backend,
            "status": "healthy" if settings.job_queue_backend in {"local", "redis"} else "not_configured",
        },
        **providers,
    }
