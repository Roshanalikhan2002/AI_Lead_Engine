from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.tenant import TenantDep
from app.models.contact_discovery import ContactDiscovery
from app.models.contact_discovery_job import ContactDiscoveryJob
from app.models.email_verification import EmailVerification
from app.models.lead import Lead
from app.models.lead_contact import LeadContact
from app.schemas.contacts import (
    BatchDiscoverContactsRequest,
    ContactDiscoveryRead,
    ContactJobStatusResponse,
    DiscoverContactsResponse,
    LeadContactRead,
)
from app.schemas.verification import EmailVerificationRead
from app.services.contacts.discovery import run_contact_discovery_job

router = APIRouter(tags=["contacts"])


@router.post(
    "/api/leads/{lead_id}/discover-contacts",
    response_model=DiscoverContactsResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def discover_contacts(
    lead_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    tenant: TenantDep,
    db: Session = Depends(get_db),
) -> DiscoverContactsResponse:
    from app.api.tenant_resources import get_org_lead_or_404
    from app.services.billing.guards import enforce_usage

    lead = get_org_lead_or_404(db, lead_id, tenant.organization_id)
    enforce_usage(db, tenant.organization_id, "emails_discovered", amount=1)
    return _enqueue(db, background_tasks, [lead.id])


@router.post(
    "/api/leads/{lead_id}/contacts/rediscover",
    response_model=DiscoverContactsResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def rediscover_contacts(
    lead_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> DiscoverContactsResponse:
    lead = db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return _enqueue(db, background_tasks, [lead_id])


@router.get("/api/leads/{lead_id}/contacts", response_model=list[LeadContactRead])
def list_contacts(lead_id: uuid.UUID, db: Session = Depends(get_db)) -> list[LeadContactRead]:
    lead = db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    contacts = (
        db.query(LeadContact)
        .filter(LeadContact.lead_id == lead_id)
        .order_by(LeadContact.is_primary.desc(), LeadContact.created_at.asc())
        .all()
    )
    verifications = {
        row.lead_contact_id: row
        for row in db.query(EmailVerification)
        .filter(EmailVerification.lead_contact_id.in_([c.id for c in contacts] or [uuid.uuid4()]))
        .all()
    }
    return [_serialize_contact(c, verifications.get(c.id)) for c in contacts]


def _serialize_contact(contact: LeadContact, verification: EmailVerification | None) -> LeadContactRead:
    payload = LeadContactRead.model_validate(contact)
    if verification:
        payload.verification = EmailVerificationRead.model_validate(verification)
        payload.verification_status = verification.status
    else:
        payload.verification_status = "not_verified"
    return payload


@router.get("/api/leads/{lead_id}/contact-discovery", response_model=ContactDiscoveryRead)
def get_contact_discovery(lead_id: uuid.UUID, db: Session = Depends(get_db)) -> ContactDiscovery:
    lead = db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    discovery = db.query(ContactDiscovery).filter(ContactDiscovery.lead_id == lead_id).one_or_none()
    if not discovery:
        raise HTTPException(status_code=404, detail="Contact discovery not found")
    return discovery


@router.post(
    "/api/leads/contacts/discover-batch",
    response_model=DiscoverContactsResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def discover_batch(
    payload: BatchDiscoverContactsRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> DiscoverContactsResponse:
    if payload.lead_ids:
        lead_ids = list(dict.fromkeys(payload.lead_ids))
    else:
        query = db.query(Lead.id)
        if payload.website_exists is True:
            query = query.filter(Lead.website.isnot(None), Lead.website != "")
        elif payload.website_exists is False:
            query = query.filter((Lead.website.is_(None)) | (Lead.website == ""))
        if payload.country:
            query = query.filter(Lead.country == payload.country)
        if payload.industry:
            query = query.filter(Lead.industry == payload.industry)
        if payload.without_contacts:
            discovered = db.query(ContactDiscovery.lead_id).filter(
                ContactDiscovery.status.in_(["completed", "no_public_email", "running"])
            )
            query = query.filter(~Lead.id.in_(discovered))
        lead_ids = [row[0] for row in query.limit(payload.limit).all()]

    if not lead_ids:
        raise HTTPException(status_code=400, detail="No leads matched the contact discovery request")
    return _enqueue(
        db,
        background_tasks,
        lead_ids,
        filters={
            "website_exists": payload.website_exists,
            "without_contacts": payload.without_contacts,
            "country": payload.country,
            "industry": payload.industry,
        },
    )


@router.get("/api/leads/contact-jobs/{job_id}", response_model=ContactJobStatusResponse)
def get_contact_job(job_id: uuid.UUID, db: Session = Depends(get_db)) -> ContactJobStatusResponse:
    job = db.get(ContactDiscoveryJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Contact discovery job not found")
    total = max(job.total, 1)
    if job.status == "completed":
        progress = 100
    elif job.status == "pending":
        progress = 0
    else:
        progress = min(99, int((job.processed / total) * 100))
    return ContactJobStatusResponse(
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
) -> DiscoverContactsResponse:
    for lead_id in lead_ids:
        existing = db.query(ContactDiscovery).filter(ContactDiscovery.lead_id == lead_id).one_or_none()
        if existing is None:
            db.add(ContactDiscovery(lead_id=lead_id, status="pending"))
        else:
            existing.status = "pending"
            existing.error_message = None
    job = ContactDiscoveryJob(
        status="pending",
        lead_ids=[str(x) for x in lead_ids],
        filters=filters,
        total=len(lead_ids),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    background_tasks.add_task(run_contact_discovery_job, job.id)
    return DiscoverContactsResponse(job_id=job.id, status="pending", lead_ids=lead_ids)
