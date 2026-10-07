from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.models.ai_qualification import AIQualification
from app.models.email_verification import EmailVerification
from app.models.lead import Lead
from app.models.lead_contact import LeadContact
from app.models.outreach_draft import OutreachDraft
from app.models.outreach_generation_job import OutreachGenerationJob
from app.schemas.outreach import (
    BatchOutreachRequest,
    OutreachDraftRead,
    OutreachGenerateRequest,
    OutreachGenerateResponse,
    OutreachJobStatusResponse,
    OutreachUpdateRequest,
)
from app.services.outreach.context import ContactSelectionError
from app.services.outreach.service import (
    generate_outreach_draft,
    run_outreach_generation_job,
    set_draft_status,
    update_outreach_draft,
)

router = APIRouter(tags=["outreach"])


def _enrich_draft(db: Session, draft: OutreachDraft) -> OutreachDraftRead:
    payload = OutreachDraftRead.model_validate(draft)
    contact = db.get(LeadContact, draft.contact_id)
    if contact:
        payload.contact_email = contact.normalized_email or contact.email
        ver = (
            db.query(EmailVerification)
            .filter(EmailVerification.lead_contact_id == contact.id)
            .one_or_none()
        )
        payload.contact_verification_status = ver.status if ver else "not_verified"
    return payload


@router.post("/api/leads/{lead_id}/outreach/generate", response_model=OutreachGenerateResponse)
def generate_for_lead(
    lead_id: uuid.UUID,
    payload: OutreachGenerateRequest | None = None,
    db: Session = Depends(get_db),
) -> OutreachGenerateResponse:
    if not db.get(Lead, lead_id):
        raise HTTPException(status_code=404, detail="Lead not found")
    contact_id = payload.contact_id if payload else None
    try:
        draft = generate_outreach_draft(db, lead_id, contact_id=contact_id, force=False)
    except ContactSelectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return OutreachGenerateResponse(
        status=draft.generation_status or draft.status,
        draft=_enrich_draft(db, draft),
    )


@router.post("/api/leads/{lead_id}/outreach/regenerate", response_model=OutreachGenerateResponse)
def regenerate_for_lead(
    lead_id: uuid.UUID,
    payload: OutreachGenerateRequest | None = None,
    db: Session = Depends(get_db),
) -> OutreachGenerateResponse:
    if not db.get(Lead, lead_id):
        raise HTTPException(status_code=404, detail="Lead not found")
    contact_id = payload.contact_id if payload else None
    try:
        draft = generate_outreach_draft(db, lead_id, contact_id=contact_id, force=True)
    except ContactSelectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return OutreachGenerateResponse(
        status=draft.generation_status or draft.status,
        draft=_enrich_draft(db, draft),
    )


@router.get("/api/leads/{lead_id}/outreach", response_model=list[OutreachDraftRead])
def list_lead_outreach(lead_id: uuid.UUID, db: Session = Depends(get_db)) -> list[OutreachDraftRead]:
    if not db.get(Lead, lead_id):
        raise HTTPException(status_code=404, detail="Lead not found")
    drafts = (
        db.query(OutreachDraft)
        .filter(OutreachDraft.lead_id == lead_id)
        .order_by(OutreachDraft.updated_at.desc())
        .all()
    )
    return [_enrich_draft(db, d) for d in drafts]


@router.get("/api/outreach/{draft_id}", response_model=OutreachDraftRead)
def get_draft(draft_id: uuid.UUID, db: Session = Depends(get_db)) -> OutreachDraftRead:
    draft = db.get(OutreachDraft, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    return _enrich_draft(db, draft)


@router.post("/api/outreach/{draft_id}/regenerate", response_model=OutreachGenerateResponse)
def regenerate_draft(draft_id: uuid.UUID, db: Session = Depends(get_db)) -> OutreachGenerateResponse:
    draft = db.get(OutreachDraft, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    try:
        new_draft = generate_outreach_draft(
            db, draft.lead_id, contact_id=draft.contact_id, force=True
        )
    except ContactSelectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return OutreachGenerateResponse(
        status=new_draft.generation_status or new_draft.status,
        draft=_enrich_draft(db, new_draft),
    )


@router.patch("/api/outreach/{draft_id}", response_model=OutreachDraftRead)
def patch_draft(
    draft_id: uuid.UUID,
    payload: OutreachUpdateRequest,
    db: Session = Depends(get_db),
) -> OutreachDraftRead:
    try:
        draft = update_outreach_draft(
            db,
            draft_id,
            subject=payload.selected_subject,
            body=payload.body,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _enrich_draft(db, draft)


@router.post("/api/outreach/{draft_id}/approve", response_model=OutreachDraftRead)
def approve_draft(draft_id: uuid.UUID, db: Session = Depends(get_db)) -> OutreachDraftRead:
    """Marks draft approved. Does NOT send email."""
    try:
        draft = set_draft_status(db, draft_id, "approved")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        from app.services.system.audit import write_audit

        write_audit(
            db,
            action="email_approved",
            entity_type="outreach_draft",
            entity_id=str(draft.id),
            metadata={"lead_id": str(draft.lead_id)},
        )
    except Exception:  # noqa: BLE001
        pass
    return _enrich_draft(db, draft)


@router.post("/api/outreach/{draft_id}/reject", response_model=OutreachDraftRead)
def reject_draft(draft_id: uuid.UUID, db: Session = Depends(get_db)) -> OutreachDraftRead:
    try:
        draft = set_draft_status(db, draft_id, "rejected")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _enrich_draft(db, draft)


@router.post(
    "/api/outreach/generate-batch",
    response_model=OutreachJobStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def generate_batch(
    payload: BatchOutreachRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> OutreachJobStatusResponse:
    settings = get_settings()
    limit = min(payload.limit, settings.outreach_max_batch)

    if payload.lead_ids:
        lead_ids = list(dict.fromkeys(payload.lead_ids))[:limit]
    else:
        query = db.query(Lead.id)
        if payload.only_qualified:
            query = query.join(AIQualification, AIQualification.lead_id == Lead.id).filter(
                AIQualification.status == "qualified",
                AIQualification.primary_service.isnot(None),
                AIQualification.primary_service != "unknown",
            )
        if payload.priority:
            query = query.join(AIQualification, AIQualification.lead_id == Lead.id).filter(
                AIQualification.priority == payload.priority
            )
        if payload.country:
            query = query.filter(Lead.country == payload.country)
        if payload.industry:
            query = query.filter(Lead.industry == payload.industry)
        if payload.only_verified_contacts:
            query = (
                query.join(LeadContact, LeadContact.lead_id == Lead.id)
                .join(EmailVerification, EmailVerification.lead_contact_id == LeadContact.id)
                .filter(EmailVerification.status == "valid")
            )
        if payload.without_current_draft:
            existing = db.query(OutreachDraft.lead_id).filter(
                OutreachDraft.status.in_(["draft", "edited", "approved"]),
                OutreachDraft.generation_status == "generated",
            )
            query = query.filter(~Lead.id.in_(existing))
        lead_ids = [row[0] for row in query.distinct().order_by(Lead.created_at.desc()).limit(limit).all()]

    if not lead_ids:
        raise HTTPException(status_code=400, detail="No leads matched the outreach generation request")

    job = OutreachGenerationJob(
        status="pending",
        lead_ids=[str(x) for x in lead_ids],
        filters={
            "only_qualified": payload.only_qualified,
            "only_verified_contacts": payload.only_verified_contacts,
            "without_current_draft": payload.without_current_draft,
            "priority": payload.priority,
        },
        total=len(lead_ids),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    background_tasks.add_task(run_outreach_generation_job, job.id)
    return _job_response(job)


@router.get("/api/outreach/jobs/{job_id}", response_model=OutreachJobStatusResponse)
def get_outreach_job(job_id: uuid.UUID, db: Session = Depends(get_db)) -> OutreachJobStatusResponse:
    job = db.get(OutreachGenerationJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Outreach generation job not found")
    return _job_response(job)


def _job_response(job: OutreachGenerationJob) -> OutreachJobStatusResponse:
    total = max(job.total, 1)
    if job.status == "completed":
        progress = 100
    elif job.status == "pending":
        progress = 0
    else:
        progress = min(99, int((job.processed / total) * 100))
    return OutreachJobStatusResponse(
        job_id=job.id,
        status=job.status,
        total=job.total,
        processed=job.processed,
        generated=job.generated_count,
        skipped=job.skipped_count,
        failed=job.failed_count,
        progress=progress,
        error_message=job.error_message,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )
