"""Inbound email intake, classification, suggestions, and campaign stop."""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.ai_qualification import AIQualification
from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage
from app.models.inbound_email import InboundEmail
from app.models.lead import Lead
from app.models.lead_contact import LeadContact
from app.models.outreach_draft import OutreachDraft
from app.models.reply_classification import ReplyClassification
from app.models.reply_suggestion import ReplySuggestion
from app.services.campaigns.events import apply_recipient_event, stop_recipients_for_email
from app.services.replies.constants import INTENT_TO_CONVERSATION_STATUS
from app.services.replies.matching import match_inbound
from app.services.replies.providers import (
    get_reply_classification_provider,
    get_reply_suggestion_provider,
)
from app.services.sending.suppression import add_suppression, normalize_email

logger = logging.getLogger(__name__)


def _hash_payload(parts: dict[str, Any]) -> str:
    raw = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _parse_received_at(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str) and value.strip():
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def ingest_inbound_email(
    db: Session,
    *,
    provider: str,
    payload: dict[str, Any],
    auto_process: bool = True,
) -> InboundEmail:
    """Persist and optionally classify an inbound reply. Never auto-sends."""
    settings = get_settings()
    provider_message_id = (
        payload.get("provider_message_id")
        or payload.get("message_id")
        or payload.get("id")
    )
    if provider_message_id:
        existing = (
            db.query(InboundEmail)
            .filter(
                InboundEmail.provider == provider,
                InboundEmail.provider_message_id == str(provider_message_id),
            )
            .one_or_none()
        )
        if existing:
            return existing

    from_email = normalize_email(
        str(payload.get("from_email") or payload.get("from") or payload.get("sender") or "")
    )
    if not from_email:
        raise ValueError("from_email_required")

    body = str(payload.get("body") or payload.get("text") or payload.get("html") or "")
    subject = payload.get("subject")
    thread_id = payload.get("thread_id") or payload.get("conversation_id")
    in_reply_to = payload.get("in_reply_to") or payload.get("inReplyTo")
    references = payload.get("references") or payload.get("references_header")
    to_email = payload.get("to_email") or payload.get("to")
    if isinstance(to_email, list) and to_email:
        to_email = to_email[0]
    if isinstance(to_email, dict):
        to_email = to_email.get("email")

    match = match_inbound(
        db,
        from_email=from_email,
        thread_id=str(thread_id) if thread_id else None,
        in_reply_to=str(in_reply_to) if in_reply_to else None,
        references_header=str(references) if references else None,
        provider_message_id=str(provider_message_id) if provider_message_id else None,
    )

    inbound = InboundEmail(
        provider=provider,
        provider_message_id=str(provider_message_id) if provider_message_id else None,
        thread_id=str(thread_id) if thread_id else None,
        message_id_header=payload.get("message_id_header"),
        in_reply_to=str(in_reply_to) if in_reply_to else None,
        references_header=str(references) if references else None,
        lead_id=match.lead_id,
        contact_id=match.contact_id,
        from_email=from_email,
        to_email=normalize_email(str(to_email)) if to_email else None,
        subject=str(subject)[:500] if subject else None,
        body=body,
        received_at=_parse_received_at(payload.get("received_at") or payload.get("timestamp")),
        processing_status="received",
        classification_status="pending",
        match_confidence=match.confidence,
        match_method=match.method,
    )
    db.add(inbound)
    db.flush()

    conversation = _ensure_conversation(db, inbound, match)
    inbound.conversation_id = conversation.id
    db.add(
        ConversationMessage(
            conversation_id=conversation.id,
            inbound_email_id=inbound.id,
            direction="inbound",
            message_type="email",
            provider_message_id=inbound.provider_message_id,
            sender_email=inbound.from_email,
            recipient_email=inbound.to_email,
            subject=inbound.subject,
            body=inbound.body,
            received_at=inbound.received_at,
        )
    )
    conversation.last_message_at = inbound.received_at
    if match.confidence == "none":
        conversation.status = "needs_human"

    # Reliable match → stop campaign follow-ups immediately
    if match.confidence in {"high", "medium"} and inbound.from_email:
        stop_recipients_for_email(
            db,
            inbound.from_email,
            event_type="reply",
            provider_event_id=inbound.provider_message_id,
        )

    db.commit()
    db.refresh(inbound)

    if auto_process and settings.reply_auto_classify:
        try:
            process_inbound(db, inbound.id, auto_suggest=settings.reply_auto_suggest)
        except Exception:  # noqa: BLE001
            logger.exception("Auto-process inbound failed id=%s", inbound.id)
            inbound = db.get(InboundEmail, inbound.id) or inbound

    return inbound


def _ensure_conversation(db: Session, inbound: InboundEmail, match) -> Conversation:
    if match.conversation_id:
        conv = db.get(Conversation, match.conversation_id)
        if conv:
            if inbound.thread_id and not conv.provider_thread_id:
                conv.provider_thread_id = inbound.thread_id
            return conv

    if match.contact_id and match.lead_id:
        existing = (
            db.query(Conversation)
            .filter(
                Conversation.lead_id == match.lead_id,
                Conversation.contact_id == match.contact_id,
            )
            .order_by(Conversation.updated_at.desc())
            .first()
        )
        if existing:
            if inbound.thread_id and not existing.provider_thread_id:
                existing.provider_thread_id = inbound.thread_id
            if match.campaign_id and not existing.campaign_id:
                existing.campaign_id = match.campaign_id
            return existing

    conv = Conversation(
        lead_id=match.lead_id,
        contact_id=match.contact_id,
        campaign_id=match.campaign_id,
        status="open" if match.confidence in {"high", "medium"} else "needs_human",
        provider_thread_id=inbound.thread_id,
        last_message_at=inbound.received_at,
    )
    db.add(conv)
    db.flush()
    return conv


def build_classification_context(db: Session, inbound: InboundEmail) -> dict[str, Any]:
    return {
        "inbound_reply": {
            "from_email": inbound.from_email,
            "subject": inbound.subject,
            "body": inbound.body,
            "received_at": inbound.received_at.isoformat() if inbound.received_at else None,
        }
    }


def build_suggestion_context(db: Session, inbound: InboundEmail, classification: ReplyClassification | None) -> dict:
    settings = get_settings()
    business: dict = {}
    contact: dict = {}
    qualification: dict = {}
    outreach: dict = {}
    if inbound.lead_id:
        lead = db.get(Lead, inbound.lead_id)
        if lead:
            business = {
                "name": lead.company_name,
                "website": lead.website,
                "city": getattr(lead, "city", None),
            }
        qual = (
            db.query(AIQualification).filter(AIQualification.lead_id == inbound.lead_id).one_or_none()
        )
        if qual:
            qualification = {
                "primary_service": qual.primary_service,
                "priority": qual.priority,
                "lead_score": qual.lead_score,
                "qualification_summary": qual.qualification_summary,
            }
        draft = (
            db.query(OutreachDraft)
            .filter(OutreachDraft.lead_id == inbound.lead_id, OutreachDraft.status == "approved")
            .order_by(OutreachDraft.updated_at.desc())
            .first()
        )
        if draft:
            outreach = {"subject": draft.selected_subject, "service": draft.service}
    if inbound.contact_id:
        c = db.get(LeadContact, inbound.contact_id)
        if c:
            contact = {"email": c.normalized_email or c.email}
    return {
        "business": business,
        "contact": contact,
        "qualification": qualification,
        "original_outreach": outreach,
        "inbound_reply": {
            "subject": inbound.subject,
            "body": inbound.body,
            "from_email": inbound.from_email,
        },
        "classification": {
            "intent": classification.intent if classification else None,
            "sentiment": classification.sentiment if classification else None,
            "reason": classification.reason if classification else None,
        },
        "agency_name": settings.agency_name,
        "pricing_known": False,
    }


def classify_inbound(
    db: Session,
    inbound_id: uuid.UUID,
    *,
    force: bool = False,
) -> ReplyClassification:
    settings = get_settings()
    inbound = db.get(InboundEmail, inbound_id)
    if not inbound:
        raise ValueError("inbound_not_found")

    context = build_classification_context(db, inbound)
    input_hash = _hash_payload(
        {
            "body": inbound.body,
            "subject": inbound.subject,
            "prompt": settings.reply_prompt_version,
            "provider": (settings.ai_provider or "").lower(),
        }
    )
    if not force:
        cached = (
            db.query(ReplyClassification)
            .filter(
                ReplyClassification.inbound_email_id == inbound.id,
                ReplyClassification.input_hash == input_hash,
            )
            .order_by(ReplyClassification.created_at.desc())
            .first()
        )
        if cached:
            return cached

    provider = get_reply_classification_provider(settings)
    result = provider.classify(context)

    row = ReplyClassification(
        inbound_email_id=inbound.id,
        conversation_id=inbound.conversation_id,
        intent=result.intent,
        intent_confidence=result.intent_confidence,
        sentiment=result.sentiment,
        sentiment_confidence=result.sentiment_confidence,
        urgency=result.urgency,
        requires_human=result.requires_human,
        reason=result.reason,
        evidence=result.evidence,
        model=result.model,
        model_version=result.model_version,
        prompt_version=result.prompt_version or settings.reply_prompt_version,
        input_hash=input_hash,
        provider=result.provider,
    )
    db.add(row)
    inbound.classification_status = "classified" if not result.error else "failed"
    inbound.processing_status = "processed"

    if inbound.conversation_id:
        conv = db.get(Conversation, inbound.conversation_id)
        if conv:
            conv.last_intent = result.intent
            conv.status = INTENT_TO_CONVERSATION_STATUS.get(result.intent, "needs_human")
            if result.intent == "unsubscribe":
                add_suppression(db, inbound.from_email, reason="unsubscribe", source="reply_classification")
                stop_recipients_for_email(db, inbound.from_email, event_type="unsubscribe")
            elif result.intent in {"not_interested", "meeting_request", "interested", "complaint"}:
                stop_recipients_for_email(db, inbound.from_email, event_type="reply")

    db.commit()
    db.refresh(row)

    if not result.error and inbound.organization_id:
        try:
            from app.services.billing.usage import increment_usage

            increment_usage(db, inbound.organization_id, "ai_reply_classifications", amount=1, check=False)
        except Exception:  # noqa: BLE001
            logger.exception("usage increment ai_reply_classifications failed")

    if result.intent == "meeting_request" and inbound.lead_id:
        from app.services.meetings.pipeline import ensure_pipeline_at_least

        ensure_pipeline_at_least(
            db,
            inbound.lead_id,
            "meeting_requested",
            reason="Reply classified as meeting_request",
            source="reply",
        )
    return row


def generate_suggestion(
    db: Session,
    conversation_id: uuid.UUID,
    *,
    inbound_id: uuid.UUID | None = None,
    force: bool = False,
) -> ReplySuggestion:
    settings = get_settings()
    conv = db.get(Conversation, conversation_id)
    if not conv:
        raise ValueError("conversation_not_found")

    inbound: InboundEmail | None = None
    if inbound_id:
        inbound = db.get(InboundEmail, inbound_id)
    elif conv.id:
        inbound = (
            db.query(InboundEmail)
            .filter(InboundEmail.conversation_id == conv.id)
            .order_by(InboundEmail.received_at.desc())
            .first()
        )
    if not inbound:
        raise ValueError("inbound_required")

    classification = (
        db.query(ReplyClassification)
        .filter(ReplyClassification.inbound_email_id == inbound.id)
        .order_by(ReplyClassification.created_at.desc())
        .first()
    )
    if classification and classification.intent == "unsubscribe":
        raise ValueError("no_suggestion_for_unsubscribe")

    context = build_suggestion_context(db, inbound, classification)
    input_hash = _hash_payload(
        {
            "inbound": inbound.id,
            "intent": classification.intent if classification else None,
            "prompt": settings.reply_prompt_version,
            "provider": (settings.ai_provider or "").lower(),
        }
    )
    if not force:
        cached = (
            db.query(ReplySuggestion)
            .filter(
                ReplySuggestion.conversation_id == conversation_id,
                ReplySuggestion.input_hash == input_hash,
                ReplySuggestion.status.in_(["draft", "edited", "approved"]),
            )
            .order_by(ReplySuggestion.created_at.desc())
            .first()
        )
        if cached:
            return cached

    provider = get_reply_suggestion_provider(settings)
    result = provider.suggest(context)
    if result.status in {"unconfigured", "error"} and not result.body:
        raise ValueError(result.error or result.status)
    if result.status == "insufficient_data" and not result.body:
        raise ValueError(result.error or "insufficient_data")

    suggestion = ReplySuggestion(
        conversation_id=conversation_id,
        inbound_email_id=inbound.id,
        subject=result.subject,
        body=result.body,
        status="draft",
        model=result.model,
        model_version=result.model_version,
        prompt_version=result.prompt_version or settings.reply_prompt_version,
        input_hash=input_hash,
        provider=result.provider,
    )
    db.add(suggestion)
    db.commit()
    db.refresh(suggestion)
    if conv.organization_id:
        try:
            from app.services.billing.usage import increment_usage

            increment_usage(db, conv.organization_id, "ai_reply_suggestions", amount=1, check=False)
        except Exception:  # noqa: BLE001
            logger.exception("usage increment ai_reply_suggestions failed")
    return suggestion


def process_inbound(
    db: Session,
    inbound_id: uuid.UUID,
    *,
    auto_suggest: bool = True,
) -> dict:
    inbound = db.get(InboundEmail, inbound_id)
    if not inbound:
        raise ValueError("inbound_not_found")
    inbound.processing_status = "processing"
    db.commit()

    classification = classify_inbound(db, inbound_id, force=False)
    suggestion = None
    if (
        auto_suggest
        and inbound.conversation_id
        and classification.intent
        not in {"unsubscribe", "not_interested", "out_of_office", "automatic_reply"}
    ):
        try:
            suggestion = generate_suggestion(db, inbound.conversation_id, inbound_id=inbound.id)
        except ValueError:
            suggestion = None

    return {
        "inbound_id": str(inbound_id),
        "classification_id": str(classification.id),
        "suggestion_id": str(suggestion.id) if suggestion else None,
        "intent": classification.intent,
    }
