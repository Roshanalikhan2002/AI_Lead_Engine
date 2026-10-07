"""Phase 8 campaign API schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CampaignStepCreate(BaseModel):
    step_number: int = Field(ge=1, le=50)
    type: str = Field(default="email")
    delay_minutes: int = Field(default=0, ge=0, le=60 * 24 * 90)
    outreach_draft_id: UUID | None = None


class CampaignStepUpdate(BaseModel):
    step_number: int | None = Field(default=None, ge=1, le=50)
    delay_minutes: int | None = Field(default=None, ge=0, le=60 * 24 * 90)
    outreach_draft_id: UUID | None = None
    type: str | None = None


class CampaignStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    campaign_id: UUID
    step_number: int
    type: str
    delay_minutes: int
    outreach_draft_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    timezone: str = Field(default="UTC", max_length=64)
    daily_send_limit: int = Field(default=50, ge=1, le=10_000)
    hourly_send_limit: int = Field(default=10, ge=1, le=1_000)
    send_start_hour: int | None = Field(default=None, ge=0, le=23)
    send_end_hour: int | None = Field(default=None, ge=1, le=24)
    send_on_weekends: bool = False
    start_at: datetime | None = None
    end_at: datetime | None = None
    steps: list[CampaignStepCreate] | None = None


class CampaignUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    timezone: str | None = Field(default=None, max_length=64)
    daily_send_limit: int | None = Field(default=None, ge=1, le=10_000)
    hourly_send_limit: int | None = Field(default=None, ge=1, le=1_000)
    send_start_hour: int | None = Field(default=None, ge=0, le=23)
    send_end_hour: int | None = Field(default=None, ge=1, le=24)
    send_on_weekends: bool | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None


class CampaignRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None = None
    status: str
    timezone: str
    daily_send_limit: int
    hourly_send_limit: int
    send_start_hour: int
    send_end_hour: int
    send_on_weekends: bool
    start_at: datetime | None = None
    end_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    # Optional list enrichment
    recipients_count: int | None = None
    active_count: int | None = None
    replied_count: int | None = None
    sent_count: int | None = None
    delivered_count: int | None = None
    bounced_count: int | None = None
    completed_count: int | None = None


class CampaignRecipientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    campaign_id: UUID
    lead_id: UUID
    contact_id: UUID
    outreach_draft_id: UUID
    status: str
    current_step: int
    next_action_at: datetime | None = None
    enrolled_at: datetime
    completed_at: datetime | None = None
    last_sent_at: datetime | None = None
    last_error: str | None = None
    business_name: str | None = None
    email: str | None = None


class EnrollRequest(BaseModel):
    lead_id: UUID
    contact_id: UUID | None = None
    draft_id: UUID | None = None


class EnrollBatchRequest(BaseModel):
    lead_ids: list[UUID] | None = None
    min_score: int | None = Field(default=None, ge=0, le=100)
    priority: str | None = None
    primary_service: str | None = None
    require_valid_email: bool = True
    require_approved_draft: bool = True


class EnrollResponse(BaseModel):
    enrolled: bool
    reason: str | None = None
    recipient_id: UUID | None = None
    lead_id: UUID | None = None
    contact_id: UUID | None = None


class RecipientEventCreate(BaseModel):
    event_type: str = Field(min_length=3, max_length=32)
    provider_event_id: str | None = None
    metadata: dict | None = None


class RecipientEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    campaign_recipient_id: UUID
    event_type: str
    provider_event_id: str | None = None
    created_at: datetime


class CampaignAnalyticsResponse(BaseModel):
    campaign_id: str
    status: str
    recipients: int
    active: int
    completed: int
    sent: int
    delivered: int
    bounced: int
    replied: int
    unsubscribed: int
    failed: int
    delivery_rate: float | None = None
    reply_rate: float | None = None
    bounce_rate: float | None = None
    unsubscribe_rate: float | None = None
    reply_detection_configured: bool = False
    reply_detection_note: str = "Reply detection provider not configured"
    has_send_data: bool = False
    status_breakdown: dict[str, int] = Field(default_factory=dict)


class ProcessDueResponse(BaseModel):
    processed: int
    results: list[dict]
