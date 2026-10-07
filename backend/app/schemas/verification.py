from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


VerificationStatus = Literal["pending", "valid", "invalid", "risky", "unknown", "blocked", "error"]


class EmailVerificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lead_contact_id: UUID
    status: VerificationStatus
    provider: str
    provider_summary: str | None = None
    is_valid: bool | None = None
    is_risky: bool | None = None
    is_disposable: bool | None = None
    is_role_based: bool | None = None
    is_free_provider: bool | None = None
    mx_found: bool | None = None
    domain: str | None = None
    verified_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class VerifyStartResponse(BaseModel):
    job_id: UUID | None = None
    status: str
    verification: EmailVerificationRead | None = None


class BatchVerifyRequest(BaseModel):
    contact_ids: list[UUID] | None = None
    lead_ids: list[UUID] | None = None
    only_unverified: bool | None = True
    discovery_confidence: Literal["high", "medium", "low"] | None = None
    country: str | None = None
    industry: str | None = None
    limit: int = Field(default=50, ge=1, le=500)


class VerificationJobStatusResponse(BaseModel):
    job_id: UUID
    status: str
    total: int
    processed: int
    valid: int
    invalid: int
    risky: int
    unknown: int
    failed: int
    progress: int
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
