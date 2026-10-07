"""Recipient stop events — architecture for future reply/webhook providers."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.campaign import Campaign
from app.models.campaign_recipient import CampaignRecipient
from app.models.lead_contact import LeadContact
from app.models.recipient_event import RecipientEvent
from app.services.campaigns.states import assert_recipient_transition, maybe_complete_campaign
from app.services.sending.suppression import add_suppression, normalize_email


EVENT_STATUS_MAP = {
    "reply": "replied",
    "bounce": "bounced",
    "unsubscribe": "unsubscribed",
    "complaint": "unsubscribed",
    "manual_stop": "cancelled",
}


def apply_recipient_event(
    db: Session,
    campaign_recipient_id: uuid.UUID,
    *,
    event_type: str,
    provider_event_id: str | None = None,
    metadata: dict | None = None,
) -> RecipientEvent:
    recipient = db.get(CampaignRecipient, campaign_recipient_id)
    if not recipient:
        raise ValueError("recipient_not_found")

    et = (event_type or "").strip().lower()
    if et not in EVENT_STATUS_MAP:
        raise ValueError(f"unsupported_event_type:{et}")

    event = RecipientEvent(
        campaign_recipient_id=recipient.id,
        event_type=et,
        provider_event_id=provider_event_id,
        metadata_json=metadata or {},
    )
    db.add(event)

    target = EVENT_STATUS_MAP[et]
    if recipient.status not in {
        "completed",
        "replied",
        "bounced",
        "unsubscribed",
        "failed",
        "cancelled",
    }:
        assert_recipient_transition(recipient.status, target)
        recipient.status = target
        recipient.completed_at = datetime.now(timezone.utc)
        recipient.next_action_at = None
        recipient.locked_at = None
        recipient.locked_by = None

    contact = db.get(LeadContact, recipient.contact_id)
    if contact and et in {"unsubscribe", "complaint", "bounce"}:
        email = normalize_email(contact.normalized_email or contact.email)
        reason = "unsubscribe" if et == "unsubscribe" else ("complaint" if et == "complaint" else "hard_bounce")
        add_suppression(db, email, reason=reason, source=f"campaign_event:{et}")

    campaign = db.get(Campaign, recipient.campaign_id)
    db.commit()
    db.refresh(event)
    if campaign:
        maybe_complete_campaign(db, campaign)
    return event


def stop_recipients_for_email(
    db: Session,
    email: str,
    *,
    event_type: str,
    provider_event_id: str | None = None,
) -> int:
    """Stop all active campaign recipients matching an email (webhook bridge)."""
    normalized = normalize_email(email)
    contacts = (
        db.query(LeadContact)
        .filter(
            (LeadContact.normalized_email == normalized) | (LeadContact.email == normalized)
        )
        .all()
    )
    if not contacts:
        return 0

    contact_ids = [c.id for c in contacts]
    recipients = (
        db.query(CampaignRecipient)
        .filter(
            CampaignRecipient.contact_id.in_(contact_ids),
            CampaignRecipient.status.in_(["pending", "active", "paused"]),
        )
        .all()
    )
    count = 0
    for recipient in recipients:
        apply_recipient_event(
            db,
            recipient.id,
            event_type=event_type,
            provider_event_id=provider_event_id,
            metadata={"source": "email_match"},
        )
        count += 1
    return count
