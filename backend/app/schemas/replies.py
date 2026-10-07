"""Phase 9 conversation / reply API schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lead_id: UUID | None = None
    contact_id: UUID | None = None
    campaign_id: UUID | None = None
    status: str
    provider_thread_id: str | None = None
    last_intent: str | None = None
    last_message_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    business_name: str | None = None
    contact_email: str | None = None
    preview: str | None = None


class ConversationMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conversation_id: UUID
    direction: str
    message_type: str
    provider_message_id: str | None = None
    sender_email: str | None = None
    recipient_email: str | None = None
    subject: str | None = None
    body: str
    sent_at: datetime | None = None
    received_at: datetime | None = None
    created_at: datetime


class ReplyClassificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    inbound_email_id: UUID
    conversation_id: UUID | None = None
    intent: str
    intent_confidence: float | None = None
    sentiment: str
    sentiment_confidence: float | None = None
    urgency: str
    requires_human: bool
    reason: str | None = None
    evidence: list | None = None
    model: str | None = None
    model_version: str | None = None
    prompt_version: str | None = None
    provider: str
    created_at: datetime


class ReplySuggestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conversation_id: UUID
    inbound_email_id: UUID | None = None
    subject: str | None = None
    body: str
    status: str
    model: str | None = None
    model_version: str | None = None
    prompt_version: str | None = None
    provider: str
    created_at: datetime
    updated_at: datetime


class ReplySuggestionUpdate(BaseModel):
    subject: str | None = None
    body: str | None = Field(default=None, min_length=1)


class InboundSimulateRequest(BaseModel):
    """Test/dev helper — also used by mock inbound webhooks."""

    from_email: str
    to_email: str | None = None
    subject: str | None = None
    body: str
    provider_message_id: str | None = None
    thread_id: str | None = None
    in_reply_to: str | None = None
    auto_process: bool = True


class ReplyAnalyticsResponse(BaseModel):
    total_replies: int
    conversations: int
    interested: int
    meeting_requests: int
    questions: int
    not_interested: int
    unsubscribes: int
    unknown: int
    reply_rate: float | None = None
    interest_rate: float | None = None
    meeting_request_rate: float | None = None
    unsubscribe_rate: float | None = None
    has_real_data: bool
    reply_tracking_live: bool = False
    note: str | None = None
