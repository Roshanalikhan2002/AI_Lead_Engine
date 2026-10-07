"""Phase 10 meeting / pipeline / booking API schemas."""

from __future__ import annotations

from datetime import date, datetime, time
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MeetingTypeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    duration_minutes: int = Field(default=30, ge=5, le=480)
    buffer_before_minutes: int = Field(default=0, ge=0, le=120)
    buffer_after_minutes: int = Field(default=0, ge=0, le=120)
    active: bool = True


class MeetingTypeUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    duration_minutes: int | None = Field(default=None, ge=5, le=480)
    buffer_before_minutes: int | None = None
    buffer_after_minutes: int | None = None
    active: bool | None = None


class MeetingTypeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None = None
    duration_minutes: int
    buffer_before_minutes: int
    buffer_after_minutes: int
    active: bool
    created_at: datetime
    updated_at: datetime


class AvailabilityRuleCreate(BaseModel):
    day_of_week: int = Field(ge=0, le=6)
    start_time: time
    end_time: time
    timezone: str = "UTC"
    active: bool = True


class AvailabilityRuleUpdate(BaseModel):
    day_of_week: int | None = Field(default=None, ge=0, le=6)
    start_time: time | None = None
    end_time: time | None = None
    timezone: str | None = None
    active: bool | None = None


class AvailabilityRuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    day_of_week: int
    start_time: time
    end_time: time
    timezone: str
    active: bool


class AvailabilityExceptionCreate(BaseModel):
    date: date
    start_time: time | None = None
    end_time: time | None = None
    type: str = "blocked"
    reason: str | None = None


class SlotRead(BaseModel):
    start_at: datetime
    end_at: datetime
    timezone: str


class MeetingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lead_id: UUID | None = None
    contact_id: UUID | None = None
    conversation_id: UUID | None = None
    campaign_id: UUID | None = None
    meeting_type_id: UUID
    status: str
    title: str
    description: str | None = None
    start_at: datetime
    end_at: datetime
    timezone: str
    meeting_url: str | None = None
    external_event_id: str | None = None
    external_provider: str | None = None
    prospect_name: str | None = None
    prospect_email: str | None = None
    outcome: str | None = None
    created_at: datetime
    updated_at: datetime
    business_name: str | None = None
    meeting_type_name: str | None = None
    calendar_live: bool = False


class BookMeetingRequest(BaseModel):
    token: str | None = None
    meeting_type_id: UUID | None = None
    start_at: datetime
    timezone: str = "UTC"
    prospect_name: str = Field(min_length=1, max_length=255)
    prospect_email: str = Field(min_length=3, max_length=255)
    prospect_message: str | None = None
    lead_id: UUID | None = None
    contact_id: UUID | None = None
    conversation_id: UUID | None = None
    idempotency_key: str | None = None


class RescheduleRequest(BaseModel):
    start_at: datetime
    timezone: str | None = None
    reason: str | None = None


class CompleteMeetingRequest(BaseModel):
    outcome: str | None = "unknown"
    notes: str | None = None


class BookingTokenCreate(BaseModel):
    meeting_type_id: UUID
    lead_id: UUID | None = None
    contact_id: UUID | None = None
    conversation_id: UUID | None = None


class BookingTokenPublic(BaseModel):
    token: str
    meeting_type: MeetingTypeRead
    timezone: str
    business_name: str | None = None
    expires_at: datetime
    calendar_live: bool = False


class PipelineStageUpdate(BaseModel):
    stage: str
    reason: str | None = None


class PipelineEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lead_id: UUID
    from_stage: str | None = None
    to_stage: str
    reason: str | None = None
    source: str
    created_by: str | None = None
    created_at: datetime


class PipelineStatsResponse(BaseModel):
    total_leads: int
    by_stage: dict[str, int]
    qualified: int
    contacted: int
    replied: int
    meeting_requested: int
    meeting_scheduled: int
    meeting_completed: int
    proposal: int
    won: int
    lost: int
    meetings_scheduled_count: int
    meetings_completed_count: int
    meeting_request_classifications: int
    replies: int
    qualification_rate: float | None = None
    reply_rate: float | None = None
    meeting_request_rate: float | None = None
    booking_rate: float | None = None
    meeting_completion_rate: float | None = None
    proposal_rate: float | None = None
    win_rate: float | None = None
    has_real_data: bool
    calendar_live: bool = False
    revenue: None = None
    note: str | None = None
