"""Orchestrates approved-draft email sending - never auto-sends."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.email_message import EmailMessage
from app.models.email_verification import EmailVerification
from app.models.lead import Lead
from app.models.lead_contact import LeadContact
from app.models.outreach_draft import OutreachDraft
from app.services.sending.providers import EmailSendingProvider, SendResult, get_email_sending_provider
from app.services.sending.suppression import add_suppression, is_suppressed, normalize_email

logger = logging.getLogger(__name__)


class SendError(ValueError):
    def __init__(self, message: str, *, code: str = "send_error", status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def build_unsubscribe_url(email: str) -> str:
    settings = get_settings()
    base = (settings.public_app_url or settings.frontend_url or "").rstrip("/")
    return f"{base}/unsubscribe?email={normalize_email(email)}"


def append_unsubscribe_footer(body: str, *, agency_name: str, unsubscribe_url: str) -> str:
    footer = (
        f"\n\n---\n"
        f"{agency_name}\n"
        f"To unsubscribe from future outreach emails, visit: {unsubscribe_url}\n"
    )
    if "unsubscribe" in body.lower() and unsubscribe_url in body:
        return body
    return body.rstrip() + footer


def idempotency_key_for_draft(draft_id: uuid.UUID) -> str:
    return f"draft-send:{draft_id}"


def check_rate_limits(db: Session) -> None:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    hour_ago = now - timedelta(hours=1)
    day_ago = now - timedelta(days=1)

    # Count real + simulated attempts that left the system (not blocked before provider)
    hour_count = (
        db.query(func.count(EmailMessage.id))
        .filter(
            EmailMessage.created_at >= hour_ago,
            EmailMessage.status.in_(["sent", "simulated", "delivered", "sending", "queued"]),
        )
        .scalar()
        or 0
    )
    day_count = (
        db.query(func.count(EmailMessage.id))
        .filter(
            EmailMessage.created_at >= day_ago,
            EmailMessage.status.in_(["sent", "simulated", "delivered", "sending", "queued"]),
        )
        .scalar()
        or 0
    )
    if hour_count >= settings.max_emails_per_hour:
        raise SendError("Hourly sending limit reached", code="rate_limit_exceeded", status_code=429)
    if day_count >= settings.max_emails_per_day:
        raise SendError("Daily sending limit reached", code="rate_limit_exceeded", status_code=429)


def send_approved_draft(
    db: Session,
    draft_id: uuid.UUID,
    *,
    provider: EmailSendingProvider | None = None,
    force_new: bool = False,
    idempotency_key: str | None = None,
    skip_global_rate_limit: bool = False,
) -> EmailMessage:
    """
    Send an approved outreach draft.
    Never marks delivered on accept. Campaign steps pass a unique idempotency_key.
    """
    settings = get_settings()
    draft = db.get(OutreachDraft, draft_id)
    if not draft:
        raise SendError("Draft not found", code="draft_not_found", status_code=404)

    if draft.status != "approved":
        raise SendError(
            "Only approved drafts can be sent",
            code="draft_not_approved",
            status_code=400,
        )

    if draft.organization_id:
        from app.services.billing.usage import UsageLimitError, check_limit

        try:
            check_limit(db, draft.organization_id, "emails_sent", amount=1)
        except UsageLimitError as exc:
            raise SendError(
                "Monthly email send limit reached.",
                code="USAGE_LIMIT_REACHED",
                status_code=402,
            ) from exc

    lead = db.get(Lead, draft.lead_id)
    if not lead:
        raise SendError("Lead not found", code="lead_not_found", status_code=404)

    contact = db.get(LeadContact, draft.contact_id)
    if not contact or contact.lead_id != draft.lead_id:
        raise SendError("Contact does not belong to this lead", code="contact_mismatch", status_code=400)

    recipient = normalize_email(contact.normalized_email or contact.email)
    if not recipient:
        raise SendError("Recipient email missing", code="invalid_recipient", status_code=400)

    verification = (
        db.query(EmailVerification)
        .filter(EmailVerification.lead_contact_id == contact.id)
        .one_or_none()
    )
    if not verification or verification.status != "valid":
        raise SendError(
            "Recipient must have verification_status=valid",
            code="verification_required",
            status_code=400,
        )

    if is_suppressed(db, recipient):
        raise SendError(
            "Recipient is suppressed",
            code="recipient_suppressed",
            status_code=400,
        )

    if not draft.selected_subject or not draft.body:
        raise SendError("Draft subject/body required", code="incomplete_draft", status_code=400)

    sender_email = (settings.sender_email or "").strip()
    sender_name = (settings.sender_name or settings.agency_name or "LeadFlow AI").strip()
    if not sender_email and not settings.email_test_mode:
        raise SendError("SENDER_EMAIL is not configured", code="sender_unconfigured", status_code=400)
    if not sender_email:
        sender_email = "noreply@localhost.test"

    # Idempotency: return existing successful/in-flight send for this key
    key = idempotency_key or idempotency_key_for_draft(draft.id)
    existing = (
        db.query(EmailMessage)
        .filter(EmailMessage.idempotency_key == key)
        .one_or_none()
    )
    if existing and not force_new:
        if existing.status in {"sent", "simulated", "delivered", "sending", "queued"}:
            return existing
        # Allow retry only for retryable failures below max
        if existing.status == "failed" and existing.retry_count >= settings.email_send_max_retries:
            raise SendError("Max send retries exceeded", code="max_retries", status_code=400)
        if existing.status in {"bounced", "blocked", "cancelled"}:
            raise SendError(
                f"Cannot resend message in status={existing.status}",
                code="not_retryable",
                status_code=400,
            )

    if not skip_global_rate_limit:
        check_rate_limits(db)

    # Effective test mode: always true unless send enabled AND test mode false AND provider configured
    test_mode = bool(settings.email_test_mode or not settings.email_send_enabled)
    provider = provider or get_email_sending_provider(settings)

    unsubscribe_url = build_unsubscribe_url(recipient)
    body_with_footer = append_unsubscribe_footer(
        draft.body,
        agency_name=sender_name,
        unsubscribe_url=unsubscribe_url,
    )

    if existing and existing.status == "failed" and existing.retry_count < settings.email_send_max_retries:
        message = existing
        message.retry_count += 1
        message.status = "sending"
        message.error_code = None
        message.error_message = None
        message.subject = draft.selected_subject
        message.body = body_with_footer
    else:
        message = EmailMessage(
            lead_id=draft.lead_id,
            contact_id=draft.contact_id,
            outreach_draft_id=draft.id,
            sender_email=sender_email,
            sender_name=sender_name,
            recipient_email=recipient,
            recipient_name=None,
            subject=draft.selected_subject,
            body=body_with_footer,
            provider=provider.name,
            status="sending",
            test_mode=test_mode,
            idempotency_key=key,
            retry_count=0,
        )
        db.add(message)

    db.commit()
    db.refresh(message)

    result: SendResult = provider.send_email(
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

    if result.status == "simulated":
        message.status = "simulated"
        message.sent_at = datetime.now(timezone.utc)
        # Keep draft approved - track send via EmailMessage; also mark draft for UX
        draft.status = "approved"  # draft stays approved; sending tracked on message
    elif result.status == "sent":
        message.status = "sent"
        message.sent_at = datetime.now(timezone.utc)
    elif result.status == "blocked":
        message.status = "blocked"
        message.error_code = result.error_code
        message.error_message = (result.error_message or "")[:255]
        message.failed_at = datetime.now(timezone.utc)
    else:
        message.status = "failed"
        message.error_code = result.error_code
        message.error_message = (result.error_message or "Send failed")[:255]
        message.failed_at = datetime.now(timezone.utc)
        if result.retryable and message.retry_count < settings.email_send_max_retries:
            # leave as failed; caller may retry same idempotency path
            pass

    db.commit()
    db.refresh(message)
    logger.info(
        "Email send draft=%s status=%s test_mode=%s provider=%s",
        draft_id,
        message.status,
        message.test_mode,
        message.provider,
    )
    if message.status in {"sent", "simulated"} and draft.organization_id:
        try:
            from app.services.billing.usage import increment_usage

            increment_usage(db, draft.organization_id, "emails_sent", amount=1, check=False)
        except Exception:  # noqa: BLE001
            logger.exception("usage increment emails_sent failed")
    try:
        from app.services.system.audit import write_audit

        write_audit(
            db,
            action="email_sent",
            entity_type="email_message",
            entity_id=str(message.id),
            metadata={
                "status": message.status,
                "test_mode": message.test_mode,
                "provider": message.provider,
                "lead_id": str(draft.lead_id),
            },
        )
    except Exception:  # noqa: BLE001
        logger.exception("audit email_sent failed")
    return message


def apply_webhook_event(
    db: Session,
    *,
    provider: str,
    provider_message_id: str,
    event_type: str,
    recipient_email: str | None = None,
) -> EmailMessage | None:
    """Normalize provider webhook events onto EmailMessage. Never invent delivery."""
    message = (
        db.query(EmailMessage)
        .filter(EmailMessage.provider_message_id == provider_message_id)
        .one_or_none()
    )
    if not message:
        return None

    event = (event_type or "").strip().lower()
    now = datetime.now(timezone.utc)

    if event in {"delivered", "delivery"}:
        message.status = "delivered"
        message.delivered_at = now
    elif event in {"bounced", "bounce", "hard_bounce"}:
        message.status = "bounced"
        message.failed_at = now
        email = normalize_email(recipient_email or message.recipient_email)
        add_suppression(db, email, reason="hard_bounce", source=f"webhook:{provider}")
        try:
            from app.services.campaigns.events import stop_recipients_for_email

            stop_recipients_for_email(db, email, event_type="bounce", provider_event_id=provider_message_id)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to stop campaign recipients on bounce")
    elif event in {"complained", "complaint", "spamcomplaint"}:
        message.status = "failed"
        message.error_code = "complaint"
        message.error_message = "Recipient complained"
        message.failed_at = now
        email = normalize_email(recipient_email or message.recipient_email)
        add_suppression(db, email, reason="complaint", source=f"webhook:{provider}")
        try:
            from app.services.campaigns.events import stop_recipients_for_email

            stop_recipients_for_email(db, email, event_type="complaint", provider_event_id=provider_message_id)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to stop campaign recipients on complaint")
    elif event in {"failed", "dropped", "rejected"}:
        message.status = "failed"
        message.failed_at = now
        message.error_code = message.error_code or "provider_failed"
    else:
        return message

    db.commit()
    db.refresh(message)
    return message
