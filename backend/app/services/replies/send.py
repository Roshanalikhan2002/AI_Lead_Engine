"""Send approved reply suggestions — never auto-send."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage
from app.models.email_message import EmailMessage
from app.models.email_verification import EmailVerification
from app.models.lead import Lead
from app.models.lead_contact import LeadContact
from app.models.reply_suggestion import ReplySuggestion
from app.services.sending.providers import get_email_sending_provider
from app.services.sending.service import SendError, append_unsubscribe_footer, build_unsubscribe_url, check_rate_limits
from app.services.sending.suppression import is_suppressed, normalize_email

logger = logging.getLogger(__name__)


def send_approved_suggestion(db: Session, suggestion_id: uuid.UUID) -> EmailMessage:
    settings = get_settings()
    suggestion = db.get(ReplySuggestion, suggestion_id)
    if not suggestion:
        raise SendError("Suggestion not found", code="suggestion_not_found", status_code=404)
    if suggestion.status != "approved":
        raise SendError("Only approved suggestions can be sent", code="not_approved", status_code=400)
    if not suggestion.body.strip():
        raise SendError("Suggestion body empty", code="empty_body", status_code=400)

    conversation = db.get(Conversation, suggestion.conversation_id)
    if not conversation:
        raise SendError("Conversation not found", code="conversation_not_found", status_code=404)
    if not conversation.lead_id or not conversation.contact_id:
        raise SendError("Conversation has no matched lead/contact", code="unmatched", status_code=400)

    lead = db.get(Lead, conversation.lead_id)
    contact = db.get(LeadContact, conversation.contact_id)
    if not lead or not contact or contact.lead_id != lead.id:
        raise SendError("Lead/contact ownership invalid", code="ownership", status_code=400)

    recipient = normalize_email(contact.normalized_email or contact.email)
    if not recipient:
        raise SendError("Recipient email missing", code="invalid_recipient", status_code=400)
    if is_suppressed(db, recipient):
        raise SendError("Recipient is suppressed", code="recipient_suppressed", status_code=400)

    verification = (
        db.query(EmailVerification)
        .filter(EmailVerification.lead_contact_id == contact.id)
        .one_or_none()
    )
    # Replies may go to contacts that replied even if verification drifted — still require not invalid
    if verification and verification.status == "invalid":
        raise SendError("Recipient email is invalid", code="verification_invalid", status_code=400)

    sender_email = (settings.sender_email or "").strip()
    sender_name = (settings.sender_name or settings.agency_name or "LeadFlow AI").strip()
    if not sender_email and not settings.email_test_mode:
        raise SendError("SENDER_EMAIL is not configured", code="sender_unconfigured", status_code=400)
    if not sender_email:
        sender_email = "noreply@localhost.test"

    key = f"reply-suggestion-send:{suggestion.id}"
    existing = db.query(EmailMessage).filter(EmailMessage.idempotency_key == key).one_or_none()
    if existing and existing.status in {"sent", "simulated", "delivered", "sending", "queued"}:
        return existing

    check_rate_limits(db)
    test_mode = bool(settings.email_test_mode or not settings.email_send_enabled)
    provider = get_email_sending_provider(settings)

    unsubscribe_url = build_unsubscribe_url(recipient)
    body = append_unsubscribe_footer(suggestion.body, agency_name=sender_name, unsubscribe_url=unsubscribe_url)
    subject = suggestion.subject or "Re: your message"

    message = EmailMessage(
        lead_id=lead.id,
        contact_id=contact.id,
        outreach_draft_id=None,
        reply_suggestion_id=suggestion.id,
        sender_email=sender_email,
        sender_name=sender_name,
        recipient_email=recipient,
        subject=subject[:255],
        body=body,
        provider=provider.name,
        status="sending",
        test_mode=test_mode,
        idempotency_key=key,
        retry_count=0,
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    result = provider.send_email(
        sender_email=sender_email,
        sender_name=sender_name,
        recipient_email=recipient,
        subject=message.subject,
        body=message.body,
        idempotency_key=key,
    )
    message.provider = result.provider_name
    message.test_mode = bool(result.test_mode or test_mode)
    message.provider_message_id = result.provider_message_id
    now = datetime.now(timezone.utc)
    if result.status == "simulated":
        message.status = "simulated"
        message.sent_at = now
    elif result.status == "sent":
        message.status = "sent"
        message.sent_at = now
    else:
        message.status = "failed"
        message.error_code = result.error_code
        message.error_message = (result.error_message or "Send failed")[:255]
        message.failed_at = now
        db.commit()
        raise SendError(message.error_message or "Send failed", code=message.error_code or "send_failed")

    suggestion.status = "sent"
    suggestion.email_message_id = message.id
    db.add(
        ConversationMessage(
            conversation_id=conversation.id,
            email_message_id=message.id,
            direction="outbound",
            message_type="email",
            provider_message_id=message.provider_message_id,
            sender_email=sender_email,
            recipient_email=recipient,
            subject=message.subject,
            body=message.body,
            sent_at=message.sent_at,
        )
    )
    conversation.last_message_at = message.sent_at
    db.commit()
    db.refresh(message)
    logger.info("Reply suggestion sent id=%s status=%s", suggestion_id, message.status)
    return message
