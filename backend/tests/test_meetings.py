"""Phase 10 meetings + pipeline tests — mock calendar/email only."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.core.config import get_settings
from app.core.database import get_db
from app.models.availability_rule import AvailabilityRule
from app.models.lead import Lead
from app.models.lead_contact import LeadContact
from app.models.meeting import Meeting
from app.models.meeting_type import MeetingType
from app.services.meetings.availability import MeetingAvailabilityService
from app.services.meetings.booking import (
    BookingError,
    book_meeting,
    cancel_meeting,
    complete_meeting,
    create_booking_token,
    reschedule_meeting,
)
from app.services.meetings.calendar import MockCalendarProvider, UnconfiguredCalendarProvider, get_calendar_provider
from app.services.meetings.pipeline import PipelineError, set_pipeline_stage
from app.services.replies.service import ingest_inbound_email
from app.models.email_verification import EmailVerification
from app.models.outreach_draft import OutreachDraft
from app.models.ai_qualification import AIQualification


@pytest.fixture(autouse=True)
def _meeting_env(monkeypatch):
    monkeypatch.setenv("CALENDAR_PROVIDER", "mock")
    monkeypatch.setenv("EMAIL_TEST_MODE", "true")
    monkeypatch.setenv("EMAIL_SEND_ENABLED", "false")
    monkeypatch.setenv("SENDER_EMAIL", "sender@leadflow.test")
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setenv("MEETING_DEFAULT_TIMEZONE", "UTC")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _seed_type_and_availability(db, *, duration=30):
    mt = MeetingType(
        name="AI Automation Consultation",
        description="Discovery call",
        duration_minutes=duration,
        buffer_before_minutes=0,
        buffer_after_minutes=0,
        active=True,
    )
    db.add(mt)
    for d in range(0, 5):
        db.add(
            AvailabilityRule(
                day_of_week=d,
                start_time=time(9, 0),
                end_time=time(17, 0),
                timezone="UTC",
                active=True,
            )
        )
    db.commit()
    db.refresh(mt)
    return mt


def _next_weekday(start: date | None = None) -> date:
    d = start or date.today()
    for _ in range(14):
        d = d + timedelta(days=1)
        if d.weekday() < 5:
            return d
    return d


def _seed_lead(db, email="prospect@biz.example"):
    lead = Lead(id=uuid.uuid4(), company_name="Biz", website="https://biz.example", source="mock")
    contact = LeadContact(
        id=uuid.uuid4(),
        lead_id=lead.id,
        email=email,
        normalized_email=email,
        contact_type="business",
        source="website",
        confidence="high",
        domain_match=True,
        is_primary=True,
    )
    db.add_all([lead, contact])
    db.flush()
    db.add(
        EmailVerification(
            id=uuid.uuid4(),
            lead_contact_id=contact.id,
            status="valid",
            provider="mock",
            is_valid=True,
        )
    )
    db.add(
        OutreachDraft(
            id=uuid.uuid4(),
            lead_id=lead.id,
            contact_id=contact.id,
            status="approved",
            selected_subject="Hi",
            body="Hello",
            provider="mock",
            generation_status="generated",
        )
    )
    db.add(
        AIQualification(
            id=uuid.uuid4(),
            lead_id=lead.id,
            status="qualified",
            lead_score=90,
            priority="hot",
            primary_service="appointment_automation",
            provider="mock",
        )
    )
    db.commit()
    return lead, contact


def test_calendar_providers():
    assert UnconfiguredCalendarProvider().create_event(
        title="t", description=None, start_at=datetime.now(timezone.utc), end_at=datetime.now(timezone.utc), timezone="UTC", attendee_email=None
    ).status == "unconfigured"
    mock = MockCalendarProvider().create_event(
        title="t",
        description=None,
        start_at=datetime.now(timezone.utc),
        end_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        timezone="UTC",
        attendee_email="a@b.com",
    )
    assert mock.live is False
    assert mock.external_event_id and mock.external_event_id.startswith("mock_")
    assert get_calendar_provider(get_settings()).name == "mock"


def test_slot_generation_respects_availability(db_session):
    mt = _seed_type_and_availability(db_session)
    day = _next_weekday()
    slots = MeetingAvailabilityService(db_session).generate_slots(
        mt, range_start=day, range_end=day, timezone_name="UTC"
    )
    assert len(slots) > 0
    assert all(s.start_at.weekday() < 5 for s in slots)


def test_booking_and_idempotency(db_session):
    mt = _seed_type_and_availability(db_session)
    lead, contact = _seed_lead(db_session)
    day = _next_weekday()
    slots = MeetingAvailabilityService(db_session).generate_slots(
        mt, range_start=day, range_end=day, timezone_name="UTC"
    )
    start = slots[0].start_at
    key = f"idem-{uuid.uuid4()}"
    m1 = book_meeting(
        db_session,
        meeting_type_id=mt.id,
        start_at=start,
        timezone_name="UTC",
        prospect_name="Alex",
        prospect_email="alex@biz.example",
        lead_id=lead.id,
        contact_id=contact.id,
        idempotency_key=key,
        send_confirmation=True,
    )
    m2 = book_meeting(
        db_session,
        meeting_type_id=mt.id,
        start_at=start,
        timezone_name="UTC",
        prospect_name="Alex",
        prospect_email="alex@biz.example",
        lead_id=lead.id,
        contact_id=contact.id,
        idempotency_key=key,
        send_confirmation=False,
    )
    assert m1.id == m2.id
    assert m1.status == "scheduled"
    assert m1.external_provider == "mock"
    db_session.refresh(lead)
    assert lead.pipeline_stage == "meeting_scheduled"


def test_double_booking_prevented(db_session):
    mt = _seed_type_and_availability(db_session)
    day = _next_weekday()
    slots = MeetingAvailabilityService(db_session).generate_slots(
        mt, range_start=day, range_end=day, timezone_name="UTC"
    )
    start = slots[0].start_at
    book_meeting(
        db_session,
        meeting_type_id=mt.id,
        start_at=start,
        timezone_name="UTC",
        prospect_name="A",
        prospect_email="a@x.example",
        idempotency_key=f"a-{start.isoformat()}",
        send_confirmation=False,
    )
    with pytest.raises(BookingError) as exc:
        book_meeting(
            db_session,
            meeting_type_id=mt.id,
            start_at=start,
            timezone_name="UTC",
            prospect_name="B",
            prospect_email="b@x.example",
            idempotency_key=f"b-{start.isoformat()}",
            send_confirmation=False,
        )
    assert exc.value.code == "slot_unavailable"


def test_token_booking_expired_and_public_api(client, db_session):
    mt = _seed_type_and_availability(db_session)
    lead, contact = _seed_lead(db_session)
    token_row = create_booking_token(
        db_session, meeting_type_id=mt.id, lead_id=lead.id, contact_id=contact.id
    )
    pub = client.get(f"/api/bookings/{token_row.token}")
    assert pub.status_code == 200
    assert pub.json()["calendar_live"] is False

    bad = client.get("/api/bookings/not-a-real-token")
    assert bad.status_code == 404

    day = _next_weekday()
    slots = MeetingAvailabilityService(db_session).generate_slots(
        mt, range_start=day, range_end=day, timezone_name="UTC"
    )
    booked = client.post(
        "/api/meetings/book",
        json={
            "token": token_row.token,
            "start_at": slots[0].start_at.isoformat(),
            "timezone": "UTC",
            "prospect_name": "Sam",
            "prospect_email": "sam@biz.example",
        },
    )
    assert booked.status_code == 200
    assert booked.json()["status"] == "scheduled"

    # token used
    again = client.get(f"/api/bookings/{token_row.token}")
    assert again.status_code in {400, 404}


def test_cancel_reschedule_complete(db_session):
    mt = _seed_type_and_availability(db_session)
    day = _next_weekday()
    slots = MeetingAvailabilityService(db_session).generate_slots(
        mt, range_start=day, range_end=day, timezone_name="UTC"
    )
    m = book_meeting(
        db_session,
        meeting_type_id=mt.id,
        start_at=slots[0].start_at,
        timezone_name="UTC",
        prospect_name="A",
        prospect_email="a@y.example",
        send_confirmation=False,
    )
    new_start = slots[1].start_at
    m2 = reschedule_meeting(db_session, m.id, new_start_at=new_start, timezone_name="UTC")
    assert m2.start_at.replace(tzinfo=timezone.utc) == new_start.replace(tzinfo=timezone.utc) or abs(
        (m2.start_at - new_start).total_seconds()
    ) < 2
    m3 = complete_meeting(db_session, m2.id, outcome="interested")
    assert m3.status == "completed"
    assert m3.outcome == "interested"
    # cancel another
    m4 = book_meeting(
        db_session,
        meeting_type_id=mt.id,
        start_at=slots[2].start_at,
        timezone_name="UTC",
        prospect_name="B",
        prospect_email="b@y.example",
        send_confirmation=False,
    )
    cancelled = cancel_meeting(db_session, m4.id)
    assert cancelled.status == "cancelled"


def test_meeting_request_does_not_auto_book(db_session):
    mt = _seed_type_and_availability(db_session)
    lead, contact = _seed_lead(db_session, email="meet@biz.example")
    inbound = ingest_inbound_email(
        db_session,
        provider="mock",
        payload={
            "event": "inbound",
            "from_email": "meet@biz.example",
            "body": "Yes, I'd be interested. Are you free Wednesday afternoon?",
            "provider_message_id": f"mreq-{uuid.uuid4()}",
        },
    )
    assert inbound.conversation_id
    from app.models.conversation import Conversation

    conv = db_session.get(Conversation, inbound.conversation_id)
    assert conv.status == "meeting_requested"
    db_session.refresh(lead)
    assert lead.pipeline_stage == "meeting_requested"
    assert db_session.query(Meeting).count() == 0
    # token can be created manually — still no meeting until book
    create_booking_token(
        db_session,
        meeting_type_id=mt.id,
        lead_id=lead.id,
        contact_id=contact.id,
        conversation_id=conv.id,
    )
    assert db_session.query(Meeting).count() == 0


def test_pipeline_manual_won(db_session):
    lead, _ = _seed_lead(db_session, email="won@biz.example")
    set_pipeline_stage(db_session, lead.id, "qualified", source="system", reason="AI", force=True)
    set_pipeline_stage(db_session, lead.id, "won", source="user", reason="Closed deal")
    db_session.refresh(lead)
    assert lead.pipeline_stage == "won"
    with pytest.raises(PipelineError):
        set_pipeline_stage(db_session, lead.id, "lost", source="system", reason="auto")


def test_pipeline_and_meeting_apis(client, db_session):
    mt = _seed_type_and_availability(db_session)
    types = client.get("/api/meeting-types")
    assert types.status_code == 200
    assert any(t["id"] == str(mt.id) for t in types.json())

    slots = client.get(f"/api/meeting-slots?meeting_type_id={mt.id}&timezone=UTC")
    assert slots.status_code == 200
    assert isinstance(slots.json(), list)

    board = client.get("/api/pipeline")
    assert board.status_code == 200
    assert "columns" in board.json()

    stats = client.get("/api/pipeline/stats")
    assert stats.status_code == 200
    assert stats.json()["revenue"] is None
    assert stats.json()["calendar_live"] is False

    cal = client.get("/api/calendar/status")
    assert cal.json()["calendar_live"] is False
