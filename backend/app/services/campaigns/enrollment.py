"""Campaign enrollment with ownership and eligibility checks."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.ai_qualification import AIQualification
from app.models.campaign import Campaign
from app.models.campaign_recipient import CampaignRecipient
from app.models.campaign_step import CampaignStep
from app.models.email_verification import EmailVerification
from app.models.lead import Lead
from app.models.lead_contact import LeadContact
from app.models.outreach_draft import OutreachDraft
from app.services.campaigns.scheduler import compute_next_send_at
from app.services.sending.suppression import is_suppressed, normalize_email


@dataclass
class EnrollResult:
    enrolled: bool
    reason: str | None = None
    recipient_id: uuid.UUID | None = None
    lead_id: uuid.UUID | None = None
    contact_id: uuid.UUID | None = None


def _approved_draft_for_lead(db: Session, lead_id: uuid.UUID, contact_id: uuid.UUID) -> OutreachDraft | None:
    return (
        db.query(OutreachDraft)
        .filter(
            OutreachDraft.lead_id == lead_id,
            OutreachDraft.contact_id == contact_id,
            OutreachDraft.status == "approved",
        )
        .order_by(OutreachDraft.updated_at.desc())
        .first()
    )


def enroll_recipient(
    db: Session,
    campaign_id: uuid.UUID,
    *,
    lead_id: uuid.UUID,
    contact_id: uuid.UUID | None = None,
    draft_id: uuid.UUID | None = None,
) -> EnrollResult:
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        return EnrollResult(False, reason="campaign_not_found", lead_id=lead_id)
    if campaign.status in {"cancelled", "completed"}:
        return EnrollResult(False, reason="campaign_not_enrollable", lead_id=lead_id)

    lead = db.get(Lead, lead_id)
    if not lead:
        return EnrollResult(False, reason="lead_not_found", lead_id=lead_id)

    contact: LeadContact | None
    if contact_id:
        contact = db.get(LeadContact, contact_id)
    else:
        contact = (
            db.query(LeadContact)
            .filter(LeadContact.lead_id == lead_id, LeadContact.is_primary.is_(True))
            .first()
        )
        if not contact:
            contact = (
                db.query(LeadContact).filter(LeadContact.lead_id == lead_id).order_by(LeadContact.created_at).first()
            )

    if not contact:
        return EnrollResult(False, reason="contact_not_found", lead_id=lead_id)
    if contact.lead_id != lead_id:
        return EnrollResult(
            False,
            reason="contact_ownership_mismatch",
            lead_id=lead_id,
            contact_id=contact.id,
        )

    email = normalize_email(contact.normalized_email or contact.email)
    if not email:
        return EnrollResult(False, reason="email_missing", lead_id=lead_id, contact_id=contact.id)

    verification = (
        db.query(EmailVerification)
        .filter(EmailVerification.lead_contact_id == contact.id)
        .one_or_none()
    )
    if not verification or verification.status != "valid":
        return EnrollResult(
            False,
            reason="email_not_verified_valid",
            lead_id=lead_id,
            contact_id=contact.id,
        )

    if is_suppressed(db, email):
        return EnrollResult(
            False,
            reason="recipient_suppressed",
            lead_id=lead_id,
            contact_id=contact.id,
        )

    existing = (
        db.query(CampaignRecipient)
        .filter(
            CampaignRecipient.campaign_id == campaign_id,
            CampaignRecipient.contact_id == contact.id,
        )
        .one_or_none()
    )
    if existing:
        if existing.status in {"pending", "active", "paused"}:
            return EnrollResult(
                False,
                reason="already_enrolled_active",
                lead_id=lead_id,
                contact_id=contact.id,
                recipient_id=existing.id,
            )
        return EnrollResult(
            False,
            reason="already_enrolled",
            lead_id=lead_id,
            contact_id=contact.id,
            recipient_id=existing.id,
        )

    draft: OutreachDraft | None
    if draft_id:
        draft = db.get(OutreachDraft, draft_id)
        if not draft or draft.lead_id != lead_id or draft.contact_id != contact.id:
            return EnrollResult(False, reason="draft_ownership_mismatch", lead_id=lead_id, contact_id=contact.id)
        if draft.status != "approved":
            return EnrollResult(False, reason="draft_not_approved", lead_id=lead_id, contact_id=contact.id)
    else:
        draft = _approved_draft_for_lead(db, lead_id, contact.id)
        if not draft:
            return EnrollResult(False, reason="approved_draft_required", lead_id=lead_id, contact_id=contact.id)

    steps = (
        db.query(CampaignStep)
        .filter(CampaignStep.campaign_id == campaign_id)
        .order_by(CampaignStep.step_number.asc())
        .all()
    )
    if not steps:
        return EnrollResult(False, reason="campaign_has_no_steps", lead_id=lead_id, contact_id=contact.id)

    now = datetime.now(timezone.utc)
    first_delay = int(steps[0].delay_minutes or 0)
    next_at = compute_next_send_at(campaign, now + timedelta(minutes=first_delay))

    status = "active" if campaign.status == "active" else "pending"
    recipient = CampaignRecipient(
        campaign_id=campaign_id,
        lead_id=lead_id,
        contact_id=contact.id,
        outreach_draft_id=draft.id,
        status=status,
        current_step=0,
        next_action_at=next_at if status == "active" else None,
        enrolled_at=now,
    )
    db.add(recipient)
    db.commit()
    db.refresh(recipient)
    return EnrollResult(
        True,
        recipient_id=recipient.id,
        lead_id=lead_id,
        contact_id=contact.id,
    )


def enroll_batch(
    db: Session,
    campaign_id: uuid.UUID,
    *,
    lead_ids: list[uuid.UUID] | None = None,
    min_score: int | None = None,
    priority: str | None = None,
    primary_service: str | None = None,
    require_valid_email: bool = True,
    require_approved_draft: bool = True,
) -> dict:
    """Explicit batch enrollment — never enrolls the whole DB without filters/selection."""
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        return {"enrolled": [], "skipped": [{"reason": "campaign_not_found"}]}

    if lead_ids:
        candidates = list(dict.fromkeys(lead_ids))
    else:
        if min_score is None and not priority and not primary_service:
            return {
                "enrolled": [],
                "skipped": [
                    {
                        "reason": "explicit_selection_or_filter_required",
                        "message": "Provide lead_ids or at least one filter",
                    }
                ],
                "enrolled_count": 0,
                "skipped_count": 1,
            }
        q = db.query(Lead.id).join(AIQualification, AIQualification.lead_id == Lead.id)
        if min_score is not None:
            q = q.filter(AIQualification.lead_score >= min_score)
        if priority:
            q = q.filter(AIQualification.priority == priority)
        if primary_service:
            q = q.filter(AIQualification.primary_service == primary_service)
        candidates = [row[0] for row in q.all()]

    enrolled: list[dict] = []
    skipped: list[dict] = []

    for lid in candidates:
        # Optional pre-filters already applied for filter path; still enforce per-recipient
        if require_valid_email or require_approved_draft:
            pass
        result = enroll_recipient(db, campaign_id, lead_id=lid)
        if result.enrolled:
            enrolled.append(
                {
                    "lead_id": str(result.lead_id),
                    "contact_id": str(result.contact_id),
                    "recipient_id": str(result.recipient_id),
                }
            )
        else:
            skipped.append(
                {
                    "lead_id": str(lid),
                    "contact_id": str(result.contact_id) if result.contact_id else None,
                    "reason": result.reason,
                }
            )

    return {"enrolled": enrolled, "skipped": skipped, "enrolled_count": len(enrolled), "skipped_count": len(skipped)}
