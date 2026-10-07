from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.models.email_verification import EmailVerification
from app.models.email_verification_job import EmailVerificationJob
from app.models.lead import Lead
from app.models.lead_contact import LeadContact
from app.schemas.verification import (
    BatchVerifyRequest,
    EmailVerificationRead,
    VerificationJobStatusResponse,
    VerifyStartResponse,
)
from app.services.verification.service import run_email_verification_job, verify_lead_contact

router = APIRouter(tags=["verification"])


@router.post(
    "/api/leads/{lead_id}/contacts/{contact_id}/verify",
    response_model=VerifyStartResponse,
)
def verify_contact_endpoint(
    lead_id: uuid.UUID,
    contact_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> VerifyStartResponse:
    from app.core.tenant import get_current_tenant
    from app.services.billing.guards import enforce_usage
    from app.services.billing.usage import UsageLimitError, increment_usage, raise_http_usage

    ctx = get_current_tenant()
    if ctx:
        enforce_usage(db, ctx.organization_id, "emails_verified", amount=1)
    try:
        row = verify_lead_contact(db, lead_id, contact_id, force=False)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if ctx and row.status not in {"error", "failed", "unconfigured"}:
        try:
            increment_usage(db, ctx.organization_id, "emails_verified", amount=1, check=False)
        except UsageLimitError as exc:
            raise_http_usage(exc)
    return VerifyStartResponse(
        job_id=None,
        status=row.status,
        verification=EmailVerificationRead.model_validate(row),
    )


@router.post(
    "/api/leads/{lead_id}/contacts/{contact_id}/reverify",
    response_model=VerifyStartResponse,
)
def reverify_contact_endpoint(
    lead_id: uuid.UUID,
    contact_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> VerifyStartResponse:
    try:
        row = verify_lead_contact(db, lead_id, contact_id, force=True)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return VerifyStartResponse(
        job_id=None,
        status=row.status,
        verification=EmailVerificationRead.model_validate(row),
    )


@router.post(
    "/api/leads/contacts/verify-batch",
    response_model=VerificationJobStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def verify_batch(
    payload: BatchVerifyRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> VerificationJobStatusResponse:
    settings = get_settings()
    limit = min(payload.limit, settings.verification_max_batch)

    if payload.contact_ids:
        contact_ids = list(dict.fromkeys(payload.contact_ids))[:limit]
    else:
        query = db.query(LeadContact.id).join(Lead, Lead.id == LeadContact.lead_id)
        if payload.lead_ids:
            query = query.filter(LeadContact.lead_id.in_(payload.lead_ids))
        if payload.country:
            query = query.filter(Lead.country == payload.country)
        if payload.industry:
            query = query.filter(Lead.industry == payload.industry)
        if payload.discovery_confidence:
            query = query.filter(LeadContact.confidence == payload.discovery_confidence)
        if payload.only_unverified:
            verified_ids = db.query(EmailVerification.lead_contact_id).filter(
                EmailVerification.status.in_(["valid", "invalid", "risky", "unknown", "blocked"])
            )
            # still allow re-queue of never-verified
            query = query.filter(~LeadContact.id.in_(verified_ids))
        contact_ids = [row[0] for row in query.limit(limit).all()]

    if not contact_ids:
        raise HTTPException(status_code=400, detail="No contacts matched the verification request")

    job = EmailVerificationJob(
        status="pending",
        contact_ids=[str(x) for x in contact_ids],
        filters={
            "only_unverified": payload.only_unverified,
            "discovery_confidence": payload.discovery_confidence,
            "country": payload.country,
            "industry": payload.industry,
        },
        total=len(contact_ids),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    background_tasks.add_task(run_email_verification_job, job.id)
    return _job_response(job)


@router.get(
    "/api/leads/contact-verification-jobs/{job_id}",
    response_model=VerificationJobStatusResponse,
)
def get_verification_job(job_id: uuid.UUID, db: Session = Depends(get_db)) -> VerificationJobStatusResponse:
    job = db.get(EmailVerificationJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Email verification job not found")
    return _job_response(job)


def _job_response(job: EmailVerificationJob) -> VerificationJobStatusResponse:
    total = max(job.total, 1)
    if job.status == "completed":
        progress = 100
    elif job.status == "pending":
        progress = 0
    else:
        progress = min(99, int((job.processed / total) * 100))
    return VerificationJobStatusResponse(
        job_id=job.id,
        status=job.status,
        total=job.total,
        processed=job.processed,
        valid=job.valid_count,
        invalid=job.invalid_count,
        risky=job.risky_count,
        unknown=job.unknown_count,
        failed=job.failed_count,
        progress=progress,
        error_message=job.error_message,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )
