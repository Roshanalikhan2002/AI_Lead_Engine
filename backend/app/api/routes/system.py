"""System health, provider status, safe provider tests, and go-live readiness."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.tenant import TenantDep, require_permission
from app.models.provider_health import ProviderOperationLog
from app.models.job_record import JobRecord
from app.models.audit_log import AuditLog
from app.services.system.config_validate import validate_production_config
from app.services.system.e2e_pipeline import provider_status_matrix, run_isolated_e2e_pipeline
from app.services.system.provider_tests import run_provider_test
from app.services.system.providers import provider_statuses, system_health
from app.services.system.readiness import production_readiness
from app.services.system.route_matrix import route_matrix

router = APIRouter(tags=["System"])


@router.get(
    "/api/health",
    summary="Basic health",
    description="Process is running. Prefer /api/health/live and /api/health/ready for probes.",
)
def health() -> dict:
    return {"status": "ok"}


@router.get(
    "/api/health/live",
    summary="Liveness probe",
    description="Returns 200 when the API process is running.",
)
def health_live() -> dict:
    return {"status": "alive"}


@router.get(
    "/api/health/ready",
    summary="Readiness probe",
    description="Database must be reachable. Does not treat provider env vars as healthy.",
)
def health_ready(db: Session = Depends(get_db)) -> dict:
    payload = system_health(db=db)
    if payload["database"]["status"] != "healthy":
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": "NOT_READY",
                    "message": "Database is not available.",
                }
            },
        )
    return {
        "status": "ready",
        "database": payload["database"],
        "config_ok": payload["config_ok"],
        "app_env": payload["app_env"],
    }


@router.get(
    "/api/system/providers",
    summary="Provider configuration status",
    description=(
        "Safe provider registry status. Never returns API keys or secrets. "
        "mode=live only after an actual successful live provider operation."
    ),
)
def list_providers(
    tenant: TenantDep,
    db: Session = Depends(get_db),
) -> dict:
    return provider_statuses(db=db, organization_id=tenant.organization_id)


@router.get(
    "/api/system/health",
    summary="Aggregated system health",
    description="Database, providers, job queue, and authentication boundary status.",
)
def get_system_health(tenant: TenantDep, db: Session = Depends(get_db)) -> dict:
    return system_health(db=db, organization_id=tenant.organization_id)


@router.post(
    "/api/system/providers/{provider}/test",
    summary="Provider health test (admin)",
    description=(
        "Admin-only. Performs the smallest safe provider operation. "
        "Never sends production email unless PROVIDER_TEST_EMAIL is set and live send flags are explicit. "
        "Never creates customer meetings or campaign sends."
    ),
)
def test_provider(
    provider: str,
    request: Request,
    tenant: TenantDep,
    db: Session = Depends(get_db),
    _perm=Depends(require_permission("integrations.manage")),
) -> dict:
    request_id = getattr(request.state, "request_id", None)
    return run_provider_test(
        db,
        provider,
        organization_id=tenant.organization_id,
        actor_user_id=tenant.user_id,
        request_id=request_id,
    )


@router.get(
    "/api/system/providers/matrix",
    summary="Provider status matrix (admin)",
    description="Honest Configured / Mode / Live-tested / Result matrix. Never invents LIVE.",
)
def providers_matrix(
    tenant: TenantDep,
    db: Session = Depends(get_db),
    _perm=Depends(require_permission("integrations.manage")),
) -> dict:
    return provider_status_matrix(db, organization_id=tenant.organization_id)


@router.post(
    "/api/system/providers/e2e-test",
    summary="Isolated provider E2E pipeline (admin)",
    description=(
        "Runs probes + one isolated provider-test lead through analysis/discovery/"
        "verification/AI/draft. Never auto-sends. Optional send_email only to PROVIDER_TEST_EMAIL."
    ),
)
def providers_e2e_test(
    request: Request,
    tenant: TenantDep,
    db: Session = Depends(get_db),
    _perm=Depends(require_permission("integrations.manage")),
    send_email: bool = False,
) -> dict:
    request_id = getattr(request.state, "request_id", None)
    return run_isolated_e2e_pipeline(
        db,
        actor_user_id=tenant.user_id,
        request_id=request_id,
        send_email=send_email,
    )


@router.get(
    "/api/system/config/validate",
    summary="Production configuration validation (admin)",
    description="Structured pass/warning/error results. Never returns secrets.",
)
def config_validate(
    _tenant: TenantDep,
    _perm=Depends(require_permission("integrations.manage")),
) -> dict:
    return validate_production_config()


@router.get(
    "/api/system/readiness",
    summary="Go-live readiness checklist (admin)",
    description="PASS only when verified. Key presence alone never implies LIVE.",
)
def readiness(
    tenant: TenantDep,
    db: Session = Depends(get_db),
    _perm=Depends(require_permission("integrations.manage")),
) -> dict:
    return production_readiness(db=db, organization_id=tenant.organization_id)


@router.get(
    "/api/system/provider-logs",
    summary="Recent provider operation logs (admin)",
    description="Safe logs only — no secrets or full email bodies.",
)
def provider_logs(
    tenant: TenantDep,
    db: Session = Depends(get_db),
    _perm=Depends(require_permission("integrations.manage")),
    limit: int = 50,
) -> dict:
    rows = (
        db.query(ProviderOperationLog)
        .filter(
            (ProviderOperationLog.organization_id == tenant.organization_id)
            | (ProviderOperationLog.organization_id.is_(None))
        )
        .order_by(ProviderOperationLog.created_at.desc())
        .limit(min(limit, 100))
        .all()
    )
    return {
        "items": [
            {
                "id": str(r.id),
                "provider": r.provider,
                "operation": r.operation,
                "status": r.status,
                "duration_ms": r.duration_ms,
                "error_code": r.error_code,
                "error_summary": r.error_summary,
                "provider_request_id": r.provider_request_id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "metadata": r.metadata_json,
            }
            for r in rows
        ]
    }


@router.get(
    "/api/system/jobs",
    summary="Recent job records (admin)",
)
def list_jobs(
    tenant: TenantDep,
    db: Session = Depends(get_db),
    _perm=Depends(require_permission("integrations.manage")),
    limit: int = 50,
) -> dict:
    rows = (
        db.query(JobRecord)
        .filter(
            (JobRecord.organization_id == tenant.organization_id) | (JobRecord.organization_id.is_(None))
        )
        .order_by(JobRecord.created_at.desc())
        .limit(min(limit, 100))
        .all()
    )
    return {
        "items": [
            {
                "id": str(r.id),
                "job_type": r.type,
                "status": r.status,
                "attempts": r.attempts,
                "last_error": r.last_error,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    }


@router.get(
    "/api/system/audit",
    summary="Recent audit events (admin)",
)
def list_audit(
    tenant: TenantDep,
    db: Session = Depends(get_db),
    _perm=Depends(require_permission("audit.view")),
    limit: int = 50,
) -> dict:
    rows = (
        db.query(AuditLog)
        .filter(AuditLog.organization_id == tenant.organization_id)
        .order_by(AuditLog.created_at.desc())
        .limit(min(limit, 100))
        .all()
    )
    return {
        "items": [
            {
                "id": str(r.id),
                "action": r.action,
                "entity_type": r.entity_type,
                "entity_id": r.entity_id,
                "actor_type": r.actor_type,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "metadata": r.metadata_json,
            }
            for r in rows
        ]
    }


@router.get(
    "/api/system/route-matrix",
    summary="Route auth/permission matrix (admin)",
    description="Documentation matrix for public exceptions and org-scoped routes.",
)
def get_route_matrix(
    _tenant: TenantDep,
    _perm=Depends(require_permission("integrations.manage")),
) -> dict:
    return {"routes": route_matrix()}
