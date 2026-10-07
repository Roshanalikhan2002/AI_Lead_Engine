from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EmailMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lead_id: UUID
    contact_id: UUID
    outreach_draft_id: UUID | None = None
    reply_suggestion_id: UUID | None = None
    sender_email: str
    sender_name: str
    recipient_email: str
    recipient_name: str | None = None
    subject: str
    body: str
    provider: str
    provider_message_id: str | None = None
    status: str
    test_mode: bool
    error_code: str | None = None
    error_message: str | None = None
    sent_at: datetime | None = None
    delivered_at: datetime | None = None
    failed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class SendEmailResponse(BaseModel):
    status: str
    message_id: UUID
    provider_message_id: str | None = None
    test_mode: bool
    error_code: str | None = None
    error_message: str | None = None


class UnsubscribeRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)


class UnsubscribeResponse(BaseModel):
    status: str
    email: str
    reason: str


class SendingStatsResponse(BaseModel):
    emails_sent: int
    delivered: int
    bounced: int
    failed: int
    suppressed: int
    simulated: int
    delivery_rate: float | None = None
    delivery_data_available: bool
    has_real_data: bool


class WebhookAckResponse(BaseModel):
    status: str
    updated: bool = False
