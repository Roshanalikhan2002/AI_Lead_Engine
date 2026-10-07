"""Phase 10 — Meetings, availability, booking, pipeline APIs."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.models.availability_exception import AvailabilityException
from app.models.availability_rule import AvailabilityRule
from app.models.booking_token import BookingToken
from app.models.lead import Lead
from app.models.lead_pipeline_event import LeadPipelineEvent
from app.models.meeting import Meeting
from app.models.meeting_type import MeetingType
from app.schemas.meetings import (
    AvailabilityExceptionCreate,
    AvailabilityRuleCreate,
    AvailabilityRuleRead,
    AvailabilityRuleUpdate,
    BookMeetingRequest,
    BookingTokenCreate,
    BookingTokenPublic,
    CompleteMeetingRequest,
    MeetingRead,
    MeetingTypeCreate,
    MeetingTypeRead,
    MeetingTypeUpdate,
    PipelineEventRead,
    PipelineStageUpdate,
    PipelineStatsResponse,
    RescheduleRequest,
    SlotRead,
)
from app.services.meetings.analytics import meeting_list_stats, pipeline_stats
from app.services.meetings.availability import MeetingAvailabilityService
from app.services.meetings.booking import (
    BookingError,
    book_meeting,
    cancel_meeting,
    complete_meeting,
    create_booking_token,
    mark_no_show,
    reschedule_meeting,
)
from app.services.meetings.calendar import get_calendar_provider
from app.services.meetings.pipeline import PIPELINE_STAGES, PipelineError, set_pipeline_stage

router = APIRouter(tags=["meetings"])


def _enrich_meeting(db: Session, m: Meeting) -> MeetingRead:
    payload = MeetingRead.model_validate(m)
    payload.calendar_live = False
    if m.lead_id:
        lead = db.get(Lead, m.lead_id)
        payload.business_name = lead.company_name if lead else None
    mt = db.get(MeetingType, m.meeting_type_id)
    payload.meeting_type_name = mt.name if mt else None
    return payload


# —— Meeting types ——
@router.get("/api/meeting-types", response_model=list[MeetingTypeRead])
def list_meeting_types(db: Session = Depends(get_db), active_only: bool = False) -> list[MeetingTypeRead]:
    q = db.query(MeetingType)
    if active_only:
        q = q.filter(MeetingType.active.is_(True))
    return [MeetingTypeRead.model_validate(r) for r in q.order_by(MeetingType.name).all()]


@router.post("/api/meeting-types", response_model=MeetingTypeRead)
def create_meeting_type(payload: MeetingTypeCreate, db: Session = Depends(get_db)) -> MeetingTypeRead:
    row = MeetingType(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return MeetingTypeRead.model_validate(row)


@router.patch("/api/meeting-types/{type_id}", response_model=MeetingTypeRead)
def update_meeting_type(
    type_id: uuid.UUID, payload: MeetingTypeUpdate, db: Session = Depends(get_db)
) -> MeetingTypeRead:
    row = db.get(MeetingType, type_id)
    if not row:
        raise HTTPException(status_code=404, detail="Meeting type not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return MeetingTypeRead.model_validate(row)


# —— Availability ——
@router.get("/api/availability", response_model=list[AvailabilityRuleRead])
def list_availability(db: Session = Depends(get_db)) -> list[AvailabilityRuleRead]:
    rows = db.query(AvailabilityRule).order_by(AvailabilityRule.day_of_week).all()
    return [AvailabilityRuleRead.model_validate(r) for r in rows]


@router.post("/api/availability", response_model=AvailabilityRuleRead)
def create_availability(payload: AvailabilityRuleCreate, db: Session = Depends(get_db)) -> AvailabilityRuleRead:
    if payload.start_time >= payload.end_time:
        raise HTTPException(status_code=400, detail="start_time must be before end_time")
    row = AvailabilityRule(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return AvailabilityRuleRead.model_validate(row)


@router.patch("/api/availability/{rule_id}", response_model=AvailabilityRuleRead)
def update_availability(
    rule_id: uuid.UUID, payload: AvailabilityRuleUpdate, db: Session = Depends(get_db)
) -> AvailabilityRuleRead:
    row = db.get(AvailabilityRule, rule_id)
    if not row:
        raise HTTPException(status_code=404, detail="Rule not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return AvailabilityRuleRead.model_validate(row)


@router.delete("/api/availability/{rule_id}", status_code=204, response_class=Response)
def delete_availability(rule_id: uuid.UUID, db: Session = Depends(get_db)) -> Response:
    row = db.get(AvailabilityRule, rule_id)
    if not row:
        raise HTTPException(status_code=404, detail="Rule not found")
    db.delete(row)
    db.commit()
    return Response(status_code=204)


@router.post("/api/availability/exceptions")
def create_exception(payload: AvailabilityExceptionCreate, db: Session = Depends(get_db)) -> dict:
    if payload.type not in {"blocked", "available"}:
        raise HTTPException(status_code=400, detail="type must be blocked or available")
    row = AvailabilityException(**payload.model_dump())
    db.add(row)
    db.commit()
    return {"id": str(row.id), "date": str(row.date), "type": row.type}


# —— Slots ——
@router.get("/api/meeting-slots", response_model=list[SlotRead])
def get_slots(
    meeting_type_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    timezone_name: str | None = Query(default=None, alias="timezone"),
    db: Session = Depends(get_db),
) -> list[SlotRead]:
    mt = db.get(MeetingType, meeting_type_id)
    if not mt or not mt.active:
        raise HTTPException(status_code=404, detail="Meeting type not found")
    settings = get_settings()
    start = start_date or date.today()
    end = end_date or (start + timedelta(days=14))
    slots = MeetingAvailabilityService(db).generate_slots(
        mt,
        range_start=start,
        range_end=end,
        timezone_name=timezone_name or settings.meeting_default_timezone,
    )
    return [SlotRead(start_at=s.start_at, end_at=s.end_at, timezone=s.timezone) for s in slots]


# —— Meetings ——
@router.get("/api/meetings", response_model=list[MeetingRead])
def list_meetings(
    status: str | None = None,
    db: Session = Depends(get_db),
) -> list[MeetingRead]:
    q = db.query(Meeting)
    if status == "upcoming":
        q = q.filter(
            Meeting.status.in_(["scheduled", "confirmed", "rescheduled"]),
            Meeting.start_at >= datetime.now(timezone.utc),
        )
    elif status == "today":
        now = datetime.now(timezone.utc)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        q = q.filter(Meeting.start_at >= start, Meeting.start_at < start + timedelta(days=1))
    elif status == "week":
        now = datetime.now(timezone.utc)
        q = q.filter(Meeting.start_at >= now, Meeting.start_at < now + timedelta(days=7))
    elif status:
        q = q.filter(Meeting.status == status)
    rows = q.order_by(Meeting.start_at.asc()).limit(200).all()
    return [_enrich_meeting(db, m) for m in rows]


@router.get("/api/meetings/stats")
def meetings_stats(db: Session = Depends(get_db)) -> dict:
    return meeting_list_stats(db)


@router.get("/api/meetings/{meeting_id}", response_model=MeetingRead)
def get_meeting(meeting_id: uuid.UUID, db: Session = Depends(get_db)) -> MeetingRead:
    m = db.get(Meeting, meeting_id)
    if not m:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return _enrich_meeting(db, m)


@router.post("/api/meetings/{meeting_id}/cancel", response_model=MeetingRead)
def api_cancel(meeting_id: uuid.UUID, db: Session = Depends(get_db)) -> MeetingRead:
    try:
        m = cancel_meeting(db, meeting_id)
    except BookingError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}) from exc
    return _enrich_meeting(db, m)


@router.post("/api/meetings/{meeting_id}/reschedule", response_model=MeetingRead)
def api_reschedule(
    meeting_id: uuid.UUID, payload: RescheduleRequest, db: Session = Depends(get_db)
) -> MeetingRead:
    try:
        m = reschedule_meeting(
            db,
            meeting_id,
            new_start_at=payload.start_at,
            timezone_name=payload.timezone,
            reason=payload.reason,
        )
    except BookingError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}) from exc
    return _enrich_meeting(db, m)


@router.post("/api/meetings/{meeting_id}/complete", response_model=MeetingRead)
def api_complete(
    meeting_id: uuid.UUID, payload: CompleteMeetingRequest | None = None, db: Session = Depends(get_db)
) -> MeetingRead:
    payload = payload or CompleteMeetingRequest()
    try:
        m = complete_meeting(db, meeting_id, outcome=payload.outcome, notes=payload.notes)
    except BookingError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}) from exc
    return _enrich_meeting(db, m)


@router.post("/api/meetings/{meeting_id}/no-show", response_model=MeetingRead)
def api_no_show(meeting_id: uuid.UUID, db: Session = Depends(get_db)) -> MeetingRead:
    try:
        m = mark_no_show(db, meeting_id)
    except BookingError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}) from exc
    return _enrich_meeting(db, m)


@router.post("/api/meetings/book", response_model=MeetingRead)
def api_book(payload: BookMeetingRequest, db: Session = Depends(get_db)) -> MeetingRead:
    try:
        m = book_meeting(
            db,
            token=payload.token,
            meeting_type_id=payload.meeting_type_id,
            start_at=payload.start_at,
            timezone_name=payload.timezone,
            prospect_name=payload.prospect_name,
            prospect_email=payload.prospect_email,
            prospect_message=payload.prospect_message,
            lead_id=payload.lead_id,
            contact_id=payload.contact_id,
            conversation_id=payload.conversation_id,
            idempotency_key=payload.idempotency_key,
        )
    except BookingError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}) from exc
    return _enrich_meeting(db, m)


# —— Booking tokens / public ——
@router.post("/api/booking-tokens")
def api_create_token(payload: BookingTokenCreate, db: Session = Depends(get_db)) -> dict:
    try:
        row = create_booking_token(
            db,
            meeting_type_id=payload.meeting_type_id,
            lead_id=payload.lead_id,
            contact_id=payload.contact_id,
            conversation_id=payload.conversation_id,
        )
    except BookingError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    settings = get_settings()
    return {
        "token": row.token,
        "booking_url": f"/book/{row.token}",
        "expires_at": row.expires_at.isoformat(),
        "calendar_provider": get_calendar_provider(settings).name,
        "calendar_live": False,
    }


@router.get("/api/bookings/{token}", response_model=BookingTokenPublic)
def public_booking(token: str, db: Session = Depends(get_db)) -> BookingTokenPublic:
    from app.services.meetings.booking import get_valid_token

    try:
        row = get_valid_token(db, token)
    except BookingError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}) from exc
    mt = db.get(MeetingType, row.meeting_type_id)
    if not mt:
        raise HTTPException(status_code=404, detail="Meeting type missing")
    settings = get_settings()
    business = None
    if row.lead_id:
        lead = db.get(Lead, row.lead_id)
        business = lead.company_name if lead else None
    return BookingTokenPublic(
        token=row.token,
        meeting_type=MeetingTypeRead.model_validate(mt),
        timezone=settings.meeting_default_timezone,
        business_name=business,
        expires_at=row.expires_at,
        calendar_live=False,
    )


@router.get("/api/calendar/status")
def calendar_status() -> dict:
    settings = get_settings()
    provider = get_calendar_provider(settings)
    return {
        "provider": provider.name,
        "configured": provider.name not in {"none", ""},
        "calendar_live": False,
        "note": "Calendar provider not live-connected. Google/Outlook not required for Phase 10.",
    }


# —— Pipeline ——
@router.get("/api/pipeline")
def pipeline_board(db: Session = Depends(get_db)) -> dict:
    from app.models.ai_qualification import AIQualification

    leads = db.query(Lead).order_by(Lead.updated_at.desc()).limit(500).all()
    columns: dict[str, list] = {s: [] for s in PIPELINE_STAGES}
    for lead in leads:
        stage = lead.pipeline_stage or "new"
        if stage not in columns:
            columns.setdefault(stage, [])
        qual = db.query(AIQualification).filter(AIQualification.lead_id == lead.id).one_or_none()
        columns[stage].append(
            {
                "id": str(lead.id),
                "company_name": lead.company_name,
                "pipeline_stage": stage,
                "lead_score": qual.lead_score if qual else None,
                "priority": qual.priority if qual else None,
                "updated_at": lead.updated_at.isoformat() if lead.updated_at else None,
            }
        )
    return {"stages": list(PIPELINE_STAGES), "columns": columns, "calendar_live": False}


@router.get("/api/pipeline/stats", response_model=PipelineStatsResponse)
def api_pipeline_stats(db: Session = Depends(get_db)) -> PipelineStatsResponse:
    return PipelineStatsResponse(**pipeline_stats(db))


@router.patch("/api/leads/{lead_id}/pipeline")
def update_lead_pipeline(
    lead_id: uuid.UUID, payload: PipelineStageUpdate, db: Session = Depends(get_db)
) -> dict:
    try:
        lead = set_pipeline_stage(
            db,
            lead_id,
            payload.stage,
            reason=payload.reason or "Manual stage change",
            source="user",
            created_by="user",
        )
    except PipelineError as exc:
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": str(exc)}) from exc
    return {"lead_id": str(lead.id), "pipeline_stage": lead.pipeline_stage}


@router.get("/api/leads/{lead_id}/pipeline-history", response_model=list[PipelineEventRead])
def pipeline_history(lead_id: uuid.UUID, db: Session = Depends(get_db)) -> list[PipelineEventRead]:
    if not db.get(Lead, lead_id):
        raise HTTPException(status_code=404, detail="Lead not found")
    rows = (
        db.query(LeadPipelineEvent)
        .filter(LeadPipelineEvent.lead_id == lead_id)
        .order_by(LeadPipelineEvent.created_at.desc())
        .all()
    )
    return [PipelineEventRead.model_validate(r) for r in rows]


@router.get("/api/leads/{lead_id}/meetings", response_model=list[MeetingRead])
def lead_meetings(lead_id: uuid.UUID, db: Session = Depends(get_db)) -> list[MeetingRead]:
    rows = (
        db.query(Meeting)
        .filter(Meeting.lead_id == lead_id)
        .order_by(Meeting.start_at.desc())
        .all()
    )
    return [_enrich_meeting(db, m) for m in rows]
