"""Phase 8 — Campaign management API."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.tenant import TenantDep, require_permission
from app.models.campaign import Campaign
from app.models.campaign_recipient import CampaignRecipient
from app.models.campaign_step import CampaignStep
from app.models.lead import Lead
from app.models.lead_contact import LeadContact
from app.models.outreach_draft import OutreachDraft
from app.models.recipient_event import RecipientEvent
from app.schemas.campaigns import (
    CampaignAnalyticsResponse,
    CampaignCreate,
    CampaignRead,
    CampaignRecipientRead,
    CampaignStepCreate,
    CampaignStepRead,
    CampaignStepUpdate,
    CampaignUpdate,
    EnrollBatchRequest,
    EnrollRequest,
    EnrollResponse,
    ProcessDueResponse,
    RecipientEventCreate,
    RecipientEventRead,
)
from app.services.campaigns.analytics import campaign_analytics
from app.services.campaigns.enrollment import enroll_batch, enroll_recipient
from app.services.campaigns.events import apply_recipient_event
from app.services.campaigns.execution import CampaignScheduler
from app.services.campaigns.scheduler import compute_next_send_at
from app.services.campaigns.states import (
    CampaignStateError,
    assert_campaign_transition,
    maybe_complete_campaign,
)
from app.services.system.audit import write_audit

router = APIRouter(tags=["campaigns"])


def _enrich_campaign(db: Session, campaign: Campaign) -> CampaignRead:
    payload = CampaignRead.model_validate(campaign)
    stats = campaign_analytics(db, campaign.id)
    payload.recipients_count = stats.get("recipients", 0)
    payload.active_count = stats.get("active", 0)
    payload.replied_count = stats.get("replied", 0)
    payload.sent_count = stats.get("sent", 0)
    payload.delivered_count = stats.get("delivered", 0)
    payload.bounced_count = stats.get("bounced", 0)
    payload.completed_count = stats.get("completed", 0)
    return payload


def _enrich_recipient(db: Session, recipient: CampaignRecipient) -> CampaignRecipientRead:
    payload = CampaignRecipientRead.model_validate(recipient)
    lead = db.get(Lead, recipient.lead_id)
    contact = db.get(LeadContact, recipient.contact_id)
    payload.business_name = lead.company_name if lead else None
    payload.email = (contact.normalized_email or contact.email) if contact else None
    return payload


def _get_campaign_or_404(db: Session, campaign_id: uuid.UUID, organization_id: uuid.UUID | None = None) -> Campaign:
    from app.core.tenant import get_current_tenant
    oid = organization_id
    if oid is None:
        ctx = get_current_tenant()
        oid = ctx.organization_id if ctx else None
    if oid is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    campaign = (
        db.query(Campaign)
        .filter(Campaign.id == campaign_id, Campaign.organization_id == oid)
        .one_or_none()
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@router.post("/api/campaigns", response_model=CampaignRead)
def create_campaign(
    payload: CampaignCreate,
    tenant: TenantDep,
    db: Session = Depends(get_db),
    _perm=Depends(require_permission("campaigns.create")),
) -> CampaignRead:
    from app.services.billing.guards import enforce_feature

    enforce_feature(db, tenant.organization_id, "campaigns")
    settings = get_settings()
    start_h = payload.send_start_hour if payload.send_start_hour is not None else settings.campaign_send_start_hour
    end_h = payload.send_end_hour if payload.send_end_hour is not None else settings.campaign_send_end_hour
    if start_h >= end_h:
        raise HTTPException(status_code=400, detail="send_start_hour must be less than send_end_hour")

    campaign = Campaign(
        organization_id=tenant.organization_id,
        name=payload.name.strip(),
        description=payload.description,
        status="draft",
        timezone=payload.timezone or settings.campaign_default_timezone,
        daily_send_limit=payload.daily_send_limit,
        hourly_send_limit=payload.hourly_send_limit,
        send_start_hour=start_h,
        send_end_hour=end_h,
        send_on_weekends=payload.send_on_weekends,
        start_at=payload.start_at,
        end_at=payload.end_at,
    )
    db.add(campaign)
    db.flush()

    steps = payload.steps or [
        CampaignStepCreate(step_number=1, delay_minutes=0),
        CampaignStepCreate(step_number=2, delay_minutes=3 * 24 * 60),
        CampaignStepCreate(step_number=3, delay_minutes=5 * 24 * 60),
    ]
    seen: set[int] = set()
    for step in steps:
        if step.type != "email":
            raise HTTPException(status_code=400, detail="Only type=email is supported in Phase 8")
        if step.step_number in seen:
            raise HTTPException(status_code=400, detail="Duplicate step_number")
        seen.add(step.step_number)
        if step.outreach_draft_id and not db.get(OutreachDraft, step.outreach_draft_id):
            raise HTTPException(status_code=400, detail="outreach_draft_id not found")
        db.add(
            CampaignStep(
                organization_id=tenant.organization_id,
                campaign_id=campaign.id,
                step_number=step.step_number,
                type="email",
                delay_minutes=step.delay_minutes,
                outreach_draft_id=step.outreach_draft_id,
            )
        )
    db.commit()
    db.refresh(campaign)
    write_audit(
        db,
        action="campaign_created",
        entity_type="campaign",
        entity_id=str(campaign.id),
        metadata={"name": campaign.name},
    )
    return _enrich_campaign(db, campaign)


@router.get("/api/campaigns", response_model=list[CampaignRead])
def list_campaigns(
    tenant: TenantDep,
    db: Session = Depends(get_db),
    _perm=Depends(require_permission("campaigns.view")),
) -> list[CampaignRead]:
    rows = (
        db.query(Campaign)
        .filter(Campaign.organization_id == tenant.organization_id)
        .order_by(Campaign.created_at.desc())
        .all()
    )
    return [_enrich_campaign(db, c) for c in rows]


@router.get("/api/campaigns/{campaign_id}", response_model=CampaignRead)
def get_campaign(campaign_id: uuid.UUID, tenant: TenantDep, db: Session = Depends(get_db), _perm=Depends(require_permission("campaigns.view"))) -> CampaignRead:
    return _enrich_campaign(db, _get_campaign_or_404(db, campaign_id, tenant.organization_id))


@router.patch("/api/campaigns/{campaign_id}", response_model=CampaignRead)
def update_campaign(
    campaign_id: uuid.UUID, payload: CampaignUpdate, tenant: TenantDep, db: Session = Depends(get_db)
) -> CampaignRead:
    campaign = _get_campaign_or_404(db, campaign_id, tenant.organization_id)
    if campaign.status in {"completed", "cancelled"}:
        raise HTTPException(status_code=400, detail="Cannot update completed/cancelled campaign")
    data = payload.model_dump(exclude_unset=True)
    if "send_start_hour" in data or "send_end_hour" in data:
        start_h = data.get("send_start_hour", campaign.send_start_hour)
        end_h = data.get("send_end_hour", campaign.send_end_hour)
        if start_h >= end_h:
            raise HTTPException(status_code=400, detail="send_start_hour must be less than send_end_hour")
    for key, value in data.items():
        setattr(campaign, key, value)
    campaign.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(campaign)
    return _enrich_campaign(db, campaign)


@router.post("/api/campaigns/{campaign_id}/activate", response_model=CampaignRead)
def activate_campaign(campaign_id: uuid.UUID, tenant: TenantDep, db: Session = Depends(get_db)) -> CampaignRead:
    from app.services.billing.guards import enforce_feature, enforce_usage

    campaign = _get_campaign_or_404(db, campaign_id, tenant.organization_id)
    enforce_feature(db, tenant.organization_id, "campaigns")
    if campaign.status != "active":
        enforce_usage(db, tenant.organization_id, "active_campaigns", amount=1)
    steps = db.query(CampaignStep).filter(CampaignStep.campaign_id == campaign_id).count()
    if steps < 1:
        raise HTTPException(status_code=400, detail="Campaign needs at least one step")
    try:
        assert_campaign_transition(campaign.status, "active")
    except CampaignStateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    campaign.status = "active"
    now = datetime.now(timezone.utc)
    campaign.updated_at = now
    # Activate pending recipients
    pending = (
        db.query(CampaignRecipient)
        .filter(CampaignRecipient.campaign_id == campaign_id, CampaignRecipient.status == "pending")
        .all()
    )
    for recipient in pending:
        recipient.status = "active"
        if recipient.next_action_at is None:
            recipient.next_action_at = compute_next_send_at(campaign, now)
    db.commit()
    db.refresh(campaign)
    write_audit(
        db,
        action="campaign_activated",
        entity_type="campaign",
        entity_id=str(campaign.id),
        metadata={"name": campaign.name},
    )
    return _enrich_campaign(db, campaign)


@router.post("/api/campaigns/{campaign_id}/pause", response_model=CampaignRead)
def pause_campaign(campaign_id: uuid.UUID, tenant: TenantDep, db: Session = Depends(get_db)) -> CampaignRead:
    campaign = _get_campaign_or_404(db, campaign_id, tenant.organization_id)
    try:
        assert_campaign_transition(campaign.status, "paused")
    except CampaignStateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    campaign.status = "paused"
    campaign.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(campaign)
    write_audit(
        db,
        action="campaign_paused",
        entity_type="campaign",
        entity_id=str(campaign.id),
    )
    return _enrich_campaign(db, campaign)


@router.post("/api/campaigns/{campaign_id}/resume", response_model=CampaignRead)
def resume_campaign(campaign_id: uuid.UUID, tenant: TenantDep, db: Session = Depends(get_db)) -> CampaignRead:
    campaign = _get_campaign_or_404(db, campaign_id, tenant.organization_id)
    if campaign.status != "paused":
        raise HTTPException(status_code=400, detail="Only paused campaigns can be resumed")
    try:
        assert_campaign_transition(campaign.status, "active")
    except CampaignStateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    campaign.status = "active"
    campaign.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(campaign)
    return _enrich_campaign(db, campaign)


@router.post("/api/campaigns/{campaign_id}/cancel", response_model=CampaignRead)
def cancel_campaign(campaign_id: uuid.UUID, tenant: TenantDep, db: Session = Depends(get_db)) -> CampaignRead:
    campaign = _get_campaign_or_404(db, campaign_id, tenant.organization_id)
    try:
        assert_campaign_transition(campaign.status, "cancelled")
    except CampaignStateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    now = datetime.now(timezone.utc)
    campaign.status = "cancelled"
    campaign.updated_at = now
    active_recipients = (
        db.query(CampaignRecipient)
        .filter(
            CampaignRecipient.campaign_id == campaign_id,
            CampaignRecipient.status.in_(["pending", "active", "paused"]),
        )
        .all()
    )
    for recipient in active_recipients:
        recipient.status = "cancelled"
        recipient.completed_at = now
        recipient.next_action_at = None
    db.commit()
    db.refresh(campaign)
    write_audit(
        db,
        action="campaign_cancelled",
        entity_type="campaign",
        entity_id=str(campaign.id),
    )
    return _enrich_campaign(db, campaign)


@router.post("/api/campaigns/{campaign_id}/enroll", response_model=EnrollResponse)
def enroll(campaign_id: uuid.UUID, payload: EnrollRequest, tenant: TenantDep, db: Session = Depends(get_db)) -> EnrollResponse:
    _get_campaign_or_404(db, campaign_id, tenant.organization_id)
    result = enroll_recipient(
        db,
        campaign_id,
        lead_id=payload.lead_id,
        contact_id=payload.contact_id,
        draft_id=payload.draft_id,
    )
    return EnrollResponse(
        enrolled=result.enrolled,
        reason=result.reason,
        recipient_id=result.recipient_id,
        lead_id=result.lead_id,
        contact_id=result.contact_id,
    )


@router.post("/api/campaigns/{campaign_id}/enroll-batch")
def enroll_many(
    campaign_id: uuid.UUID, payload: EnrollBatchRequest, tenant: TenantDep, db: Session = Depends(get_db)
) -> dict:
    _get_campaign_or_404(db, campaign_id, tenant.organization_id)
    return enroll_batch(
        db,
        campaign_id,
        lead_ids=payload.lead_ids,
        min_score=payload.min_score,
        priority=payload.priority,
        primary_service=payload.primary_service,
        require_valid_email=payload.require_valid_email,
        require_approved_draft=payload.require_approved_draft,
    )


@router.get("/api/campaigns/{campaign_id}/recipients", response_model=list[CampaignRecipientRead])
def list_recipients(campaign_id: uuid.UUID, tenant: TenantDep, db: Session = Depends(get_db)) -> list[CampaignRecipientRead]:
    _get_campaign_or_404(db, campaign_id, tenant.organization_id)
    rows = (
        db.query(CampaignRecipient)
        .filter(CampaignRecipient.campaign_id == campaign_id)
        .order_by(CampaignRecipient.enrolled_at.desc())
        .all()
    )
    return [_enrich_recipient(db, r) for r in rows]


@router.get("/api/campaigns/{campaign_id}/steps", response_model=list[CampaignStepRead])
def list_steps(campaign_id: uuid.UUID, tenant: TenantDep, db: Session = Depends(get_db)) -> list[CampaignStepRead]:
    _get_campaign_or_404(db, campaign_id, tenant.organization_id)
    rows = (
        db.query(CampaignStep)
        .filter(CampaignStep.campaign_id == campaign_id)
        .order_by(CampaignStep.step_number.asc())
        .all()
    )
    return [CampaignStepRead.model_validate(r) for r in rows]


@router.post("/api/campaigns/{campaign_id}/steps", response_model=CampaignStepRead)
def add_step(
    campaign_id: uuid.UUID,
    payload: CampaignStepCreate,
    tenant: TenantDep,
    db: Session = Depends(get_db),
) -> CampaignStepRead:
    campaign = _get_campaign_or_404(db, campaign_id, tenant.organization_id)
    if campaign.status not in {"draft", "paused"}:
        raise HTTPException(status_code=400, detail="Steps can only be added in draft or paused state")
    if payload.type != "email":
        raise HTTPException(status_code=400, detail="Only type=email is supported in Phase 8")
    exists = (
        db.query(CampaignStep)
        .filter(CampaignStep.campaign_id == campaign_id, CampaignStep.step_number == payload.step_number)
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail="step_number already exists")
    step = CampaignStep(
        organization_id=tenant.organization_id,
        campaign_id=campaign_id,
        step_number=payload.step_number,
        type="email",
        delay_minutes=payload.delay_minutes,
        outreach_draft_id=payload.outreach_draft_id,
    )
    db.add(step)
    db.commit()
    db.refresh(step)
    return CampaignStepRead.model_validate(step)


@router.patch("/api/campaigns/{campaign_id}/steps/{step_id}", response_model=CampaignStepRead)
def update_step(
    campaign_id: uuid.UUID,
    step_id: uuid.UUID,
    payload: CampaignStepUpdate,
    tenant: TenantDep,
    db: Session = Depends(get_db),
) -> CampaignStepRead:
    campaign = _get_campaign_or_404(db, campaign_id, tenant.organization_id)
    if campaign.status not in {"draft", "paused"}:
        raise HTTPException(status_code=400, detail="Steps can only be edited in draft or paused state")
    step = db.get(CampaignStep, step_id)
    if not step or step.campaign_id != campaign_id:
        raise HTTPException(status_code=404, detail="Step not found")
    data = payload.model_dump(exclude_unset=True)
    if data.get("type") and data["type"] != "email":
        raise HTTPException(status_code=400, detail="Only type=email is supported in Phase 8")
    for key, value in data.items():
        setattr(step, key, value)
    db.commit()
    db.refresh(step)
    return CampaignStepRead.model_validate(step)


@router.delete("/api/campaigns/{campaign_id}/steps/{step_id}", status_code=204, response_class=Response)
def delete_step(campaign_id: uuid.UUID, step_id: uuid.UUID, tenant: TenantDep, db: Session = Depends(get_db)) -> Response:
    campaign = _get_campaign_or_404(db, campaign_id, tenant.organization_id)
    if campaign.status not in {"draft", "paused"}:
        raise HTTPException(status_code=400, detail="Steps can only be deleted in draft or paused state")
    step = db.get(CampaignStep, step_id)
    if not step or step.campaign_id != campaign_id:
        raise HTTPException(status_code=404, detail="Step not found")
    db.delete(step)
    db.commit()
    return Response(status_code=204)


@router.get("/api/campaigns/{campaign_id}/analytics", response_model=CampaignAnalyticsResponse)
def analytics(campaign_id: uuid.UUID, tenant: TenantDep, db: Session = Depends(get_db)) -> CampaignAnalyticsResponse:
    _get_campaign_or_404(db, campaign_id, tenant.organization_id)
    data = campaign_analytics(db, campaign_id)
    return CampaignAnalyticsResponse(**data)


@router.post("/api/campaigns/process-due", response_model=ProcessDueResponse)
def process_due(db: Session = Depends(get_db), limit: int = 25) -> ProcessDueResponse:
    """Manual / cron-friendly scheduler tick (swap-ready for Celery)."""
    result = CampaignScheduler(db).tick(limit=limit)
    return ProcessDueResponse(**result)


@router.post(
    "/api/campaigns/recipients/{recipient_id}/events",
    response_model=RecipientEventRead,
)
def create_recipient_event(
    recipient_id: uuid.UUID,
    payload: RecipientEventCreate,
    db: Session = Depends(get_db),
) -> RecipientEventRead:
    """Inject stop events (reply/bounce/unsubscribe). Reply provider not live yet."""
    recipient = db.get(CampaignRecipient, recipient_id)
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")
    try:
        event = apply_recipient_event(
            db,
            recipient_id,
            event_type=payload.event_type,
            provider_event_id=payload.provider_event_id,
            metadata=payload.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RecipientEventRead(
        id=event.id,
        campaign_recipient_id=event.campaign_recipient_id,
        event_type=event.event_type,
        provider_event_id=event.provider_event_id,
        created_at=event.created_at,
    )
