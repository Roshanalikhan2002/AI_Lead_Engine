from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.tenant import TenantDep, require_permission
from app.models.generation_job import GenerationJob
from app.schemas.generation import GenerationCreateRequest, GenerationCreateResponse, GenerationStatusResponse
from app.services.auth.service import bump_usage
from app.services.billing.guards import enforce_usage
from app.services.lead_discovery import run_generation_job

router = APIRouter(tags=["Discovery"])


@router.post("/api/generation", response_model=GenerationCreateResponse, status_code=status.HTTP_202_ACCEPTED)
def create_generation(
    payload: GenerationCreateRequest,
    background_tasks: BackgroundTasks,
    tenant: TenantDep,
    db: Session = Depends(get_db),
    _perm=Depends(require_permission("leads.create")),
) -> GenerationCreateResponse:
    enforce_usage(db, tenant.organization_id, "leads_discovered", amount=max(1, payload.quantity))
    job = GenerationJob(
        organization_id=tenant.organization_id,
        status="pending",
        country=payload.country,
        state=payload.state,
        city=payload.city,
        industry=payload.industry,
        keywords=payload.keywords,
        min_rating=payload.min_rating,
        min_reviews=payload.min_reviews,
        website_filter=payload.website_filter,
        requested_quantity=payload.quantity,
    )
    db.add(job)
    bump_usage(db, tenant.organization_id, "leads_discovered", 0)
    db.commit()
    db.refresh(job)

    background_tasks.add_task(run_generation_job, job.id)
    return GenerationCreateResponse(job_id=job.id, status="pending")


@router.get("/api/generation/{job_id}", response_model=GenerationStatusResponse)
def get_generation_status(
    job_id: uuid.UUID,
    tenant: TenantDep,
    db: Session = Depends(get_db),
    _perm=Depends(require_permission("leads.view")),
) -> GenerationStatusResponse:
    job = (
        db.query(GenerationJob)
        .filter(GenerationJob.id == job_id, GenerationJob.organization_id == tenant.organization_id)
        .one_or_none()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Generation job not found")

    target = max(job.requested_quantity, 1)
    if job.status == "completed":
        progress = 100
    elif job.status == "pending":
        progress = 0
    else:
        progress = min(99, int((job.processed_quantity / target) * 100))

    return GenerationStatusResponse(
        job_id=job.id,
        status=job.status,  # type: ignore[arg-type]
        found=job.found_quantity,
        processed=job.processed_quantity,
        saved=job.saved_quantity,
        duplicates_skipped=job.duplicates_skipped,
        target=job.requested_quantity,
        progress=progress,
        country=job.country,
        state=job.state,
        city=job.city,
        industry=job.industry,
        error_message=job.error_message,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )


# Health probes live on System routes: /api/health, /api/health/live, /api/health/ready
