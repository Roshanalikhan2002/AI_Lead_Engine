from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.tenant import TenantDep
from app.api.tenant_resources import get_org_lead_or_404
from app.models.ai_qualification import AIQualification
from app.models.ai_qualification_job import AIQualificationJob
from app.models.lead import Lead
from app.models.website_analysis import WebsiteAnalysis
from app.schemas.qualification import (
    AIQualificationRead,
    BatchQualifyRequest,
    QualificationJobStatusResponse,
    QualificationStatsResponse,
    QualifyStartResponse,
)
from app.services.qualification.service import qualify_lead, run_ai_qualification_job

router = APIRouter(tags=["qualification"])


@router.post("/api/leads/{lead_id}/qualify", response_model=QualifyStartResponse)
def qualify_lead_endpoint(
    lead_id: uuid.UUID, tenant: TenantDep, db: Session = Depends(get_db)
) -> QualifyStartResponse:
    from app.services.billing.features import FeatureNotAvailable, raise_http_feature
    from app.services.billing.usage import UsageLimitError, raise_http_usage

    get_org_lead_or_404(db, lead_id, tenant.organization_id)
    try:
        row = qualify_lead(db, lead_id, force=False)
    except FeatureNotAvailable as exc:
        raise_http_feature(exc)
    except UsageLimitError as exc:
        raise_http_usage(exc)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return QualifyStartResponse(
        job_id=None,
        status=row.status,
        qualification=AIQualificationRead.model_validate(row),
    )


@router.post("/api/leads/{lead_id}/requalify", response_model=QualifyStartResponse)
def requalify_lead_endpoint(
    lead_id: uuid.UUID, tenant: TenantDep, db: Session = Depends(get_db)
) -> QualifyStartResponse:
    from app.services.billing.features import FeatureNotAvailable, raise_http_feature
    from app.services.billing.usage import UsageLimitError, raise_http_usage

    get_org_lead_or_404(db, lead_id, tenant.organization_id)
    try:
        row = qualify_lead(db, lead_id, force=True)
    except FeatureNotAvailable as exc:
        raise_http_feature(exc)
    except UsageLimitError as exc:
        raise_http_usage(exc)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return QualifyStartResponse(
        job_id=None,
        status=row.status,
        qualification=AIQualificationRead.model_validate(row),
    )


@router.get("/api/leads/{lead_id}/qualification", response_model=AIQualificationRead)
def get_qualification(
    lead_id: uuid.UUID, tenant: TenantDep, db: Session = Depends(get_db)
) -> AIQualificationRead:
    get_org_lead_or_404(db, lead_id, tenant.organization_id)
    row = db.query(AIQualification).filter(AIQualification.lead_id == lead_id).one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Qualification not found")
    return AIQualificationRead.model_validate(row)


@router.post(
    "/api/leads/qualify-batch",
    response_model=QualificationJobStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def qualify_batch(
    payload: BatchQualifyRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> QualificationJobStatusResponse:
    settings = get_settings()
    limit = min(payload.limit, settings.ai_max_batch)

    if payload.lead_ids:
        lead_ids = list(dict.fromkeys(payload.lead_ids))[:limit]
    else:
        query = db.query(Lead.id)
        if payload.country:
            query = query.filter(Lead.country == payload.country)
        if payload.industry:
            query = query.filter(Lead.industry == payload.industry)
        if payload.website_analyzed:
            query = query.join(WebsiteAnalysis, WebsiteAnalysis.lead_id == Lead.id).filter(
                WebsiteAnalysis.analysis_status == "completed"
            )
        if payload.only_unqualified:
            qualified_ids = db.query(AIQualification.lead_id).filter(
                AIQualification.status.in_(["qualified", "not_qualified", "insufficient_data"])
            )
            query = query.filter(~Lead.id.in_(qualified_ids))
        lead_ids = [row[0] for row in query.order_by(Lead.created_at.desc()).limit(limit).all()]

    if not lead_ids:
        raise HTTPException(status_code=400, detail="No leads matched the qualification request")

    job = AIQualificationJob(
        status="pending",
        lead_ids=[str(x) for x in lead_ids],
        filters={
            "only_unqualified": payload.only_unqualified,
            "country": payload.country,
            "industry": payload.industry,
            "website_analyzed": payload.website_analyzed,
        },
        total=len(lead_ids),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    background_tasks.add_task(run_ai_qualification_job, job.id)
    return _job_response(job)


@router.get(
    "/api/leads/qualification-jobs/{job_id}",
    response_model=QualificationJobStatusResponse,
)
def get_qualification_job(job_id: uuid.UUID, db: Session = Depends(get_db)) -> QualificationJobStatusResponse:
    job = db.get(AIQualificationJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="AI qualification job not found")
    return _job_response(job)


@router.get("/api/qualification/stats", response_model=QualificationStatsResponse)
def qualification_stats(db: Session = Depends(get_db)) -> QualificationStatsResponse:
    """Real qualification aggregates for dashboard — empty when no AI data exists."""
    total_qualified = (
        db.query(func.count(AIQualification.id))
        .filter(AIQualification.status == "qualified")
        .scalar()
        or 0
    )
    hot = (
        db.query(func.count(AIQualification.id))
        .filter(AIQualification.status == "qualified", AIQualification.priority == "hot")
        .scalar()
        or 0
    )
    warm = (
        db.query(func.count(AIQualification.id))
        .filter(AIQualification.status == "qualified", AIQualification.priority == "warm")
        .scalar()
        or 0
    )
    cold = (
        db.query(func.count(AIQualification.id))
        .filter(AIQualification.status == "qualified", AIQualification.priority == "cold")
        .scalar()
        or 0
    )
    avg = (
        db.query(func.avg(AIQualification.lead_score))
        .filter(AIQualification.status == "qualified", AIQualification.lead_score.isnot(None))
        .scalar()
    )
    top_opp = (
        db.query(AIQualification.primary_service, func.count(AIQualification.id))
        .filter(
            AIQualification.status == "qualified",
            AIQualification.primary_service.isnot(None),
            AIQualification.primary_service != "unknown",
        )
        .group_by(AIQualification.primary_service)
        .order_by(func.count(AIQualification.id).desc())
        .first()
    )
    top_industry = (
        db.query(Lead.industry, func.count(AIQualification.id))
        .join(AIQualification, AIQualification.lead_id == Lead.id)
        .filter(AIQualification.status == "qualified", Lead.industry.isnot(None))
        .group_by(Lead.industry)
        .order_by(func.count(AIQualification.id).desc())
        .first()
    )
    has_real = total_qualified > 0
    return QualificationStatsResponse(
        total_qualified=total_qualified,
        hot_leads=hot,
        warm_leads=warm,
        cold_leads=cold,
        average_score=round(float(avg), 1) if avg is not None and has_real else None,
        top_opportunity=top_opp[0] if top_opp and has_real else None,
        top_industry=top_industry[0] if top_industry and has_real else None,
        has_real_data=has_real,
    )


def _job_response(job: AIQualificationJob) -> QualificationJobStatusResponse:
    total = max(job.total, 1)
    if job.status == "completed":
        progress = 100
    elif job.status == "pending":
        progress = 0
    else:
        progress = min(99, int((job.processed / total) * 100))
    return QualificationJobStatusResponse(
        job_id=job.id,
        status=job.status,
        total=job.total,
        processed=job.processed,
        qualified=job.qualified_count,
        insufficient_data=job.insufficient_data_count,
        failed=job.failed_count,
        progress=progress,
        error_message=job.error_message,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )
