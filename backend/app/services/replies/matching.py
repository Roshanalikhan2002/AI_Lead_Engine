"""Match inbound emails to leads/contacts without guessing."""

from __future__ import annotations

from dataclasses import dataclass
import uuid

from sqlalchemy.orm import Session

from app.models.campaign_recipient import CampaignRecipient
from app.models.conversation import Conversation
from app.models.email_message import EmailMessage
from app.models.lead_contact import LeadContact
from app.services.sending.suppression import normalize_email


@dataclass
class MatchResult:
    lead_id: uuid.UUID | None = None
    contact_id: uuid.UUID | None = None
    campaign_id: uuid.UUID | None = None
    conversation_id: uuid.UUID | None = None
    confidence: str = "none"  # high | medium | low | none
    method: str | None = None


def _contacts_for_email(db: Session, email: str) -> list[LeadContact]:
    normalized = normalize_email(email)
    if not normalized:
        return []
    return (
        db.query(LeadContact)
        .filter(
            (LeadContact.normalized_email == normalized) | (LeadContact.email == normalized)
        )
        .all()
    )


def match_inbound(
    db: Session,
    *,
    from_email: str,
    thread_id: str | None = None,
    in_reply_to: str | None = None,
    references_header: str | None = None,
    provider_message_id: str | None = None,
) -> MatchResult:
    # 1) Existing conversation by provider thread
    if thread_id:
        conv = (
            db.query(Conversation)
            .filter(Conversation.provider_thread_id == thread_id)
            .order_by(Conversation.updated_at.desc())
            .first()
        )
        if conv and conv.lead_id and conv.contact_id:
            return MatchResult(
                lead_id=conv.lead_id,
                contact_id=conv.contact_id,
                campaign_id=conv.campaign_id,
                conversation_id=conv.id,
                confidence="high",
                method="provider_thread_id",
            )

    # 2) In-Reply-To / References → outbound EmailMessage
    candidates: list[str] = []
    if in_reply_to:
        candidates.append(in_reply_to.strip())
    if references_header:
        candidates.extend([p.strip() for p in references_header.replace(",", " ").split() if p.strip()])
    for ref in candidates:
        msg = (
            db.query(EmailMessage)
            .filter(
                (EmailMessage.provider_message_id == ref)
                | (EmailMessage.idempotency_key == ref)
            )
            .first()
        )
        if msg:
            return MatchResult(
                lead_id=msg.lead_id,
                contact_id=msg.contact_id,
                conversation_id=None,
                confidence="high",
                method="in_reply_to_outbound",
            )

    # 3) Known contact email — only if exactly one contact matches
    contacts = _contacts_for_email(db, from_email)
    if len(contacts) == 1:
        contact = contacts[0]
        campaign_id = None
        active = (
            db.query(CampaignRecipient)
            .filter(
                CampaignRecipient.contact_id == contact.id,
                CampaignRecipient.status.in_(["pending", "active", "paused"]),
            )
            .order_by(CampaignRecipient.enrolled_at.desc())
            .first()
        )
        if active:
            campaign_id = active.campaign_id
        existing = (
            db.query(Conversation)
            .filter(
                Conversation.contact_id == contact.id,
                Conversation.lead_id == contact.lead_id,
            )
            .order_by(Conversation.last_message_at.desc().nullslast())
            .first()
        )
        return MatchResult(
            lead_id=contact.lead_id,
            contact_id=contact.id,
            campaign_id=campaign_id or (existing.campaign_id if existing else None),
            conversation_id=existing.id if existing else None,
            confidence="high",
            method="contact_email_unique",
        )

    if len(contacts) > 1:
        # Ambiguous — do not guess
        return MatchResult(confidence="none", method="ambiguous_contact_email")

    return MatchResult(confidence="none", method="no_match")
