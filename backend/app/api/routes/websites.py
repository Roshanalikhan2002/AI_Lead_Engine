from __future__ import annotations

import uuid
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.tenant_resources import get_org_lead_or_404
from app.core.database import get_db
from app.core.tenant import TenantDep
from app.models.lead import Lead
from app.models.lead_opportunity import LeadOpportunity
from app.models.website_analysis import WebsiteAnalysis
from app.models.website_analysis_job import WebsiteAnalysisJob
from app.schemas.website import (
    AnalyzeStartResponse,
    BatchAnalyzeRequest,
    LeadOpportunityRead,
    WebsiteAnalysisRead,
    WebsiteJobStatusResponse,
)
from app.services.billing.guards import enforce_usage
from app.services.website.analyzer import run_website_analysis_job

router = APIRouter(tags=["websites"])


@router.post("/api/websites/analyze/{lead_id}", response_model=AnalyzeStartResponse, status_code=status.HTTP_202_ACCEPTED)
def analyze_website(
    lead_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    tenant: TenantDep,
    db: Session = Depends(get_db),
) -> AnalyzeStartResponse:
    lead = get_org_lead_or_404(db, lead_id, tenant.organization_id)
    enforce_usage(db, tenant.organization_id, "website_analyses", amount=1)
    return _enqueue(db, background_tasks, [lead.id])


@router.post("/api/leads/{lead_id}/reanalyze-website", response_model=AnalyzeStartResponse, status_code=status.HTTP_202_ACCEPTED)
def reanalyze_website(
    lead_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    tenant: TenantDep,
    db: Session = Depends(get_db),
) -> AnalyzeStartResponse:
    lead = get_org_lead_or_404(db, lead_id, tenant.organization_id)
    return _enqueue(db, background_tasks, [lead.id])


@router.get("/api/websites/{lead_id}", response_model=WebsiteAnalysisRead)
def get_website_analysis(
    lead_id: uuid.UUID, tenant: TenantDep, db: Session = Depends(get_db)
) -> WebsiteAnalysis:
    get_org_lead_or_404(db, lead_id, tenant.organization_id)
    analysis = db.query(WebsiteAnalysis).filter(WebsiteAnalysis.lead_id == lead_id).one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="Website analysis not found")
    return analysis


@router.get("/api/websites/{lead_id}/opportunities", response_model=list[LeadOpportunityRead])
def get_website_opportunities(
    lead_id: uuid.UUID, tenant: TenantDep, db: Session = Depends(get_db)
) -> list[LeadOpportunity]:
    get_org_lead_or_404(db, lead_id, tenant.organization_id)
    return (
        db.query(LeadOpportunity)
        .filter(LeadOpportunity.lead_id == lead_id)
        .order_by(LeadOpportunity.created_at.desc())
        .all()
    )


@router.post("/api/websites/analyze-batch", response_model=AnalyzeStartResponse, status_code=status.HTTP_202_ACCEPTED)
def analyze_batch(
    payload: BatchAnalyzeRequest,
    background_tasks: BackgroundTasks,
    tenant: TenantDep,
    db: Session = Depends(get_db),
) -> AnalyzeStartResponse:
    if payload.lead_ids:
        lead_ids = [
            row[0]
            for row in db.query(Lead.id)
            .filter(
                Lead.organization_id == tenant.organization_id,
                Lead.id.in_(list(dict.fromkeys(payload.lead_ids))),
            )
            .all()
        ]
    else:
        query = db.query(Lead.id).filter(Lead.organization_id == tenant.organization_id)
        if payload.website_exists is True:
            query = query.filter(Lead.website.isnot(None), Lead.website != "")
        elif payload.website_exists is False:
            query = query.filter((Lead.website.is_(None)) | (Lead.website == ""))
        if payload.country:
            query = query.filter(Lead.country == payload.country)
        if payload.industry:
            query = query.filter(Lead.industry == payload.industry)
        if payload.not_analyzed:
            analyzed_ids = db.query(WebsiteAnalysis.lead_id).filter(
                WebsiteAnalysis.analysis_status.in_(["completed", "not_available", "running"])
            )
            query = query.filter(~Lead.id.in_(analyzed_ids))
        lead_ids = [row[0] for row in query.limit(payload.limit).all()]

    if not lead_ids:
        raise HTTPException(status_code=400, detail="No leads matched the analysis request")
    return _enqueue(
        db,
        background_tasks,
        lead_ids,
        filters={
            "website_exists": payload.website_exists,
            "not_analyzed": payload.not_analyzed,
            "country": payload.country,
            "industry": payload.industry,
        },
    )


@router.get("/api/websites/jobs/{job_id}", response_model=WebsiteJobStatusResponse)
def get_website_job(
    job_id: uuid.UUID, tenant: TenantDep, db: Session = Depends(get_db)
) -> WebsiteJobStatusResponse:
    job = (
        db.query(WebsiteAnalysisJob)
        .filter(WebsiteAnalysisJob.id == job_id, WebsiteAnalysisJob.organization_id == tenant.organization_id)
        .one_or_none()
    )
    if not job:
        # Fallback for jobs created before org scoping on job row
        job = db.get(WebsiteAnalysisJob, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Website analysis job not found")
    total = max(job.total, 1)
    if job.status == "completed":
        progress = 100
    elif job.status == "pending":
        progress = 0
    else:
        progress = min(99, int((job.processed / total) * 100))
    return WebsiteJobStatusResponse(
        job_id=job.id,
        status=job.status,
        total=job.total,
        processed=job.processed,
        succeeded=job.succeeded,
        failed=job.failed,
        progress=progress,
        error_message=job.error_message,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )


def _enqueue(
    db: Session,
    background_tasks: BackgroundTasks,
    lead_ids: list[uuid.UUID],
    filters: dict | None = None,
) -> AnalyzeStartResponse:
    for lead_id in lead_ids:
        existing = db.query(WebsiteAnalysis).filter(WebsiteAnalysis.lead_id == lead_id).one_or_none()
        if existing is None:
            db.add(WebsiteAnalysis(lead_id=lead_id, analysis_status="pending"))
        else:
            existing.analysis_status = "pending"
            existing.error_message = None
    job = WebsiteAnalysisJob(
        status="pending",
        lead_ids=[str(x) for x in lead_ids],
        filters=filters,
        total=len(lead_ids),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    background_tasks.add_task(run_website_analysis_job, job.id)
    return AnalyzeStartResponse(job_id=job.id, status="pending", lead_ids=lead_ids)
