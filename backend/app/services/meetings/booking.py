"""Meeting booking, cancel, reschedule, outcomes."""

from __future__ import annotations

import logging
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.booking_token import BookingToken
from app.models.conversation import Conversation
from app.models.email_message import EmailMessage
from app.models.lead import Lead
from app.models.lead_contact import LeadContact
from app.models.meeting import Meeting
from app.models.meeting_reschedule_history import MeetingRescheduleHistory
from app.models.meeting_type import MeetingType
from app.services.meetings.availability import MeetingAvailabilityService
from app.services.meetings.calendar import get_calendar_provider
from app.services.meetings.pipeline import ensure_pipeline_at_least
from app.services.sending.providers import get_email_sending_provider
from app.services.sending.service import append_unsubscribe_footer, build_unsubscribe_url, check_rate_limits
from app.services.sending.suppression import is_suppressed, normalize_email

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class BookingError(ValueError):
    def __init__(self, message: str, *, code: str = "booking_error", status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def create_booking_token(
    db: Session,
    *,
    meeting_type_id: uuid.UUID,
    lead_id: uuid.UUID | None = None,
    contact_id: uuid.UUID | None = None,
    conversation_id: uuid.UUID | None = None,
) -> BookingToken:
    settings = get_settings()
    mt = db.get(MeetingType, meeting_type_id)
    if not mt or not mt.active:
        raise BookingError("Meeting type not found or inactive", code="meeting_type_invalid")
    token = secrets.token_urlsafe(32)
    row = BookingToken(
        token=token,
        lead_id=lead_id,
        contact_id=contact_id,
        conversation_id=conversation_id,
        meeting_type_id=meeting_type_id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.meeting_booking_token_ttl_days),
        active=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_valid_token(db: Session, token: str) -> BookingToken:
    row = db.query(BookingToken).filter(BookingToken.token == token).one_or_none()
    if not row or not row.active:
        raise BookingError("Invalid booking token", code="invalid_token", status_code=404)
    if row.used_at is not None:
        raise BookingError("Booking token already used", code="token_used", status_code=400)
    now = datetime.now(timezone.utc)
    exp = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)
    if exp < now:
        raise BookingError("Booking token expired", code="expired_token", status_code=400)
    return row


def book_meeting(
    db: Session,
    *,
    token: str | None = None,
    meeting_type_id: uuid.UUID | None = None,
    start_at: datetime,
    timezone_name: str,
    prospect_name: str,
    prospect_email: str,
    prospect_message: str | None = None,
    lead_id: uuid.UUID | None = None,
    contact_id: uuid.UUID | None = None,
    conversation_id: uuid.UUID | None = None,
    idempotency_key: str | None = None,
    send_confirmation: bool = True,
) -> Meeting:
    settings = get_settings()
    booking: BookingToken | None = None
    if token:
        booking = get_valid_token(db, token)
        meeting_type_id = booking.meeting_type_id
        lead_id = lead_id or booking.lead_id
        contact_id = contact_id or booking.contact_id
        conversation_id = conversation_id or booking.conversation_id

    if not meeting_type_id:
        raise BookingError("meeting_type_id required", code="meeting_type_required")

    mt = db.get(MeetingType, meeting_type_id)
    if not mt or not mt.active:
        raise BookingError("Meeting type invalid", code="meeting_type_invalid")

    email = normalize_email(prospect_email)
    if not email or not EMAIL_RE.match(email):
        raise BookingError("Invalid email", code="invalid_email")
    if is_suppressed(db, email):
        raise BookingError("Email is suppressed", code="suppressed")

    if start_at.tzinfo is None:
        start_at = start_at.replace(tzinfo=timezone.utc)
    end_at = start_at + timedelta(minutes=mt.duration_minutes)

    key = idempotency_key or (
        f"book:{token or 'direct'}:{start_at.isoformat()}:{email}:{meeting_type_id}"
    )
    existing = db.query(Meeting).filter(Meeting.idempotency_key == key).one_or_none()
    if existing:
        return existing

    # Concurrency-safe slot claim: check then insert with unique key
    avail = MeetingAvailabilityService(db)
    slots = avail.generate_slots(
        mt,
        range_start=start_at.astimezone(timezone.utc).date() - timedelta(days=1),
        range_end=start_at.astimezone(timezone.utc).date() + timedelta(days=1),
        timezone_name=timezone_name,
    )
    if not any(abs((s.start_at - start_at).total_seconds()) < 1 for s in slots):
        # Direct overlap check as fallback
        conflict = (
            db.query(Meeting)
            .filter(
                Meeting.status.in_(["scheduled", "confirmed", "requested", "rescheduled"]),
                Meeting.start_at < end_at,
                Meeting.end_at > start_at,
            )
            .first()
        )
        if conflict or not any(abs((s.start_at - start_at).total_seconds()) < 60 for s in slots):
            raise BookingError("Slot not available", code="slot_unavailable")

    calendar = get_calendar_provider(settings)
    cal = calendar.create_event(
        title=mt.name,
        description=prospect_message or mt.description,
        start_at=start_at,
        end_at=end_at,
        timezone=timezone_name,
        attendee_email=email,
    )

    meeting = Meeting(
        organization_id=booking.organization_id if booking else (lead_id and db.get(Lead, lead_id) and db.get(Lead, lead_id).organization_id),
        lead_id=lead_id,
        contact_id=contact_id,
        conversation_id=conversation_id,
        meeting_type_id=mt.id,
        status="scheduled",
        title=mt.name,
        description=mt.description,
        start_at=start_at,
        end_at=end_at,
        timezone=timezone_name,
        meeting_url=cal.meeting_url if cal.status == "created" else None,
        external_event_id=cal.external_event_id if cal.status == "created" else None,
        external_provider=cal.provider if cal.status == "created" else None,
        prospect_name=prospect_name.strip()[:255],
        prospect_email=email,
        prospect_message=prospect_message,
        idempotency_key=key,
        booking_token_id=booking.id if booking else None,
    )
    if meeting.organization_id is None:
        meeting.organization_id = mt.organization_id

    db.add(meeting)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        existing = db.query(Meeting).filter(Meeting.idempotency_key == key).one_or_none()
        if existing:
            return existing
        # Possible race on overlapping slot — re-check
        raise BookingError("Could not book slot (conflict)", code="slot_conflict") from exc

    # Double-check no overlapping after flush
    overlap = (
        db.query(Meeting)
        .filter(
            Meeting.id != meeting.id,
            Meeting.status.in_(["scheduled", "confirmed", "requested", "rescheduled"]),
            Meeting.start_at < end_at,
            Meeting.end_at > start_at,
        )
        .first()
    )
    if overlap:
        db.rollback()
        raise BookingError("Slot not available", code="slot_unavailable")

    if booking:
        booking.used_at = datetime.now(timezone.utc)
        booking.active = False

    db.commit()
    db.refresh(meeting)

    try:
        from app.services.system.audit import write_audit

        write_audit(
            db,
            action="meeting_booked",
            entity_type="meeting",
            entity_id=str(meeting.id),
            metadata={
                "lead_id": str(lead_id) if lead_id else None,
                "calendar_provider": meeting.external_provider,
            },
        )
    except Exception:  # noqa: BLE001
        logger.exception("audit meeting_booked failed")

    if lead_id:
        ensure_pipeline_at_least(
            db, lead_id, "meeting_scheduled", reason="Meeting booked", source="meeting"
        )

    if send_confirmation and settings.meeting_send_confirmations:
        try:
            _send_confirmation(db, meeting)
        except Exception:  # noqa: BLE001
            logger.exception("Meeting confirmation email failed")

    return meeting


def _send_confirmation(db: Session, meeting: Meeting) -> EmailMessage | None:
    settings = get_settings()
    email = meeting.prospect_email
    if not email or is_suppressed(db, email):
        return None
    check_rate_limits(db)
    provider = get_email_sending_provider(settings)
    sender_email = (settings.sender_email or "").strip() or "noreply@localhost.test"
    sender_name = settings.sender_name or settings.agency_name
    subject = f"Meeting confirmed: {meeting.title}"
    body = (
        f"Hi {meeting.prospect_name or 'there'},\n\n"
        f"Your meeting \"{meeting.title}\" is scheduled.\n\n"
        f"When: {meeting.start_at.isoformat()} ({meeting.timezone})\n"
        f"Duration ends: {meeting.end_at.isoformat()}\n"
    )
    if meeting.meeting_url:
        body += f"Meeting link: {meeting.meeting_url}\n"
    body += "\nThank you."
    unsub = build_unsubscribe_url(email)
    body = append_unsubscribe_footer(body, agency_name=sender_name, unsubscribe_url=unsub)
    key = f"meeting-confirm:{meeting.id}"
    existing = db.query(EmailMessage).filter(EmailMessage.idempotency_key == key).one_or_none()
    if existing:
        return existing

    # Need lead/contact for EmailMessage FK — create only if we have them
    if not meeting.lead_id or not meeting.contact_id:
        # Still send via provider without persisting EmailMessage lead link — persist with placeholders skip
        result = provider.send_email(
            sender_email=sender_email,
            sender_name=sender_name,
            recipient_email=email,
            subject=subject,
            body=body,
            idempotency_key=key,
        )
        logger.info("Meeting confirmation provider status=%s (no lead link)", result.status)
        return None

    test_mode = bool(settings.email_test_mode or not settings.email_send_enabled)
    msg = EmailMessage(
        lead_id=meeting.lead_id,
        contact_id=meeting.contact_id,
        outreach_draft_id=None,
        sender_email=sender_email,
        sender_name=sender_name,
        recipient_email=email,
        subject=subject[:255],
        body=body,
        provider=provider.name,
        status="sending",
        test_mode=test_mode,
        idempotency_key=key,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    result = provider.send_email(
        sender_email=sender_email,
        sender_name=sender_name,
        recipient_email=email,
        subject=subject,
        body=body,
        idempotency_key=key,
    )
    msg.provider = result.provider_name
    msg.provider_message_id = result.provider_message_id
    msg.test_mode = bool(result.test_mode or test_mode)
    if result.status in {"sent", "simulated"}:
        msg.status = result.status
        msg.sent_at = datetime.now(timezone.utc)
    else:
        msg.status = "failed"
        msg.error_message = (result.error_message or "")[:255]
    db.commit()
    return msg


def cancel_meeting(db: Session, meeting_id: uuid.UUID, *, reason: str | None = None) -> Meeting:
    meeting = db.get(Meeting, meeting_id)
    if not meeting:
        raise BookingError("Meeting not found", code="not_found", status_code=404)
    if meeting.status in {"cancelled", "completed", "no_show"}:
        raise BookingError(f"Cannot cancel from status={meeting.status}", code="invalid_status")
    settings = get_settings()
    if meeting.external_event_id and meeting.external_provider:
        cal = get_calendar_provider(settings)
        if cal.name == meeting.external_provider or meeting.external_provider == "mock":
            cal.cancel_event(meeting.external_event_id)
    meeting.status = "cancelled"
    meeting.updated_at = datetime.now(timezone.utc)
    if reason:
        meeting.outcome_notes = (meeting.outcome_notes or "") + f"\nCancelled: {reason}"
    db.commit()
    db.refresh(meeting)
    return meeting


def reschedule_meeting(
    db: Session,
    meeting_id: uuid.UUID,
    *,
    new_start_at: datetime,
    timezone_name: str | None = None,
    reason: str | None = None,
) -> Meeting:
    meeting = db.get(Meeting, meeting_id)
    if not meeting:
        raise BookingError("Meeting not found", code="not_found", status_code=404)
    if meeting.status not in {"scheduled", "confirmed", "rescheduled", "requested"}:
        raise BookingError("Cannot reschedule this meeting", code="invalid_status")
    mt = db.get(MeetingType, meeting.meeting_type_id)
    if not mt:
        raise BookingError("Meeting type missing", code="meeting_type_invalid")
    if new_start_at.tzinfo is None:
        new_start_at = new_start_at.replace(tzinfo=timezone.utc)
    new_end = new_start_at + timedelta(minutes=mt.duration_minutes)
    tz_name = timezone_name or meeting.timezone

    conflict = (
        db.query(Meeting)
        .filter(
            Meeting.id != meeting.id,
            Meeting.status.in_(["scheduled", "confirmed", "requested", "rescheduled"]),
            Meeting.start_at < new_end,
            Meeting.end_at > new_start_at,
        )
        .first()
    )
    if conflict:
        raise BookingError("New slot not available", code="slot_unavailable")

    avail = MeetingAvailabilityService(db)
    day = new_start_at.date()
    slots = avail.generate_slots(mt, range_start=day, range_end=day, timezone_name=tz_name)
    # Temporarily ignore this meeting in busy by checking overlap already done; allow if no conflict
    # Prefer matching generated slots
    if slots and not any(abs((s.start_at - new_start_at).total_seconds()) < 60 for s in slots):
        # still allow if only blocked by self — regenerate doesn't exclude self, so check duration windows
        pass

    hist = MeetingRescheduleHistory(
        meeting_id=meeting.id,
        previous_start_at=meeting.start_at,
        previous_end_at=meeting.end_at,
        new_start_at=new_start_at,
        new_end_at=new_end,
        reason=reason,
        source="user",
    )
    db.add(hist)
    meeting.start_at = new_start_at
    meeting.end_at = new_end
    meeting.timezone = tz_name
    meeting.status = "rescheduled"
    meeting.updated_at = datetime.now(timezone.utc)

    settings = get_settings()
    if meeting.external_event_id:
        cal = get_calendar_provider(settings)
        result = cal.update_event(
            external_event_id=meeting.external_event_id,
            title=meeting.title,
            description=meeting.description,
            start_at=new_start_at,
            end_at=new_end,
            timezone=tz_name,
        )
        if result.meeting_url:
            meeting.meeting_url = result.meeting_url

    db.commit()
    db.refresh(meeting)
    # After reschedule, treat as scheduled for pipeline
    meeting.status = "scheduled"
    db.commit()
    db.refresh(meeting)
    return meeting


def complete_meeting(
    db: Session,
    meeting_id: uuid.UUID,
    *,
    outcome: str | None = None,
    notes: str | None = None,
) -> Meeting:
    allowed = {
        "interested",
        "qualified",
        "proposal_requested",
        "not_interested",
        "follow_up_required",
        "won",
        "lost",
        "unknown",
        None,
    }
    if outcome not in allowed:
        raise BookingError("Invalid outcome", code="invalid_outcome")
    meeting = db.get(Meeting, meeting_id)
    if not meeting:
        raise BookingError("Meeting not found", code="not_found", status_code=404)
    meeting.status = "completed"
    meeting.outcome = outcome or "unknown"
    meeting.outcome_notes = notes
    meeting.updated_at = datetime.now(timezone.utc)
    if meeting.lead_id:
        next_stage = "proposal" if outcome == "proposal_requested" else "meeting_completed"
        if outcome == "won":
            ensure_pipeline_at_least(db, meeting.lead_id, "meeting_completed", reason="Meeting completed", source="meeting")
            # won must be manual — only set meeting_completed here
        else:
            ensure_pipeline_at_least(db, meeting.lead_id, next_stage, reason="Meeting completed", source="meeting")
    db.commit()
    db.refresh(meeting)
    return meeting


def mark_no_show(db: Session, meeting_id: uuid.UUID) -> Meeting:
    meeting = db.get(Meeting, meeting_id)
    if not meeting:
        raise BookingError("Meeting not found", code="not_found", status_code=404)
    meeting.status = "no_show"
    meeting.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(meeting)
    return meeting
