from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


DraftStatus = Literal["draft", "approved", "rejected", "edited", "cancelled"]


class OutreachDraftRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lead_id: UUID
    contact_id: UUID
    status: str
    selected_subject: str | None = None
    alternative_subjects: list[str] | None = None
    body: str | None = None
    service: str | None = None
    personalization_points: list[str] | None = None
    provider: str
    model: str | None = None
    model_version: str | None = None
    prompt_version: str | None = None
    input_hash: str | None = None
    error_message: str | None = None
    generation_status: str | None = None
    created_at: datetime
    updated_at: datetime
    # Enriched for frontend (optional)
    contact_email: str | None = None
    contact_verification_status: str | None = None


class OutreachGenerateRequest(BaseModel):
    contact_id: UUID | None = None


class OutreachGenerateResponse(BaseModel):
    job_id: UUID | None = None
    status: str
    draft: OutreachDraftRead | None = None


class OutreachUpdateRequest(BaseModel):
    selected_subject: str | None = None
    body: str | None = None


class BatchOutreachRequest(BaseModel):
    lead_ids: list[UUID] | None = None
    priority: Literal["hot", "warm", "cold"] | None = None
    only_qualified: bool | None = True
    only_verified_contacts: bool | None = True
    without_current_draft: bool | None = True
    country: str | None = None
    industry: str | None = None
    limit: int = Field(default=25, ge=1, le=200)


class OutreachJobStatusResponse(BaseModel):
    job_id: UUID
    status: str
    total: int
    processed: int
    generated: int
    skipped: int
    failed: int
    progress: int
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
