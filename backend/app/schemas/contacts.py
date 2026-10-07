from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


ContactType = Literal[
    "business",
    "sales",
    "support",
    "info",
    "marketing",
    "booking",
    "personal",
    "unknown",
]
Confidence = Literal["high", "medium", "low"]
DiscoveryStatus = Literal[
    "not_discovered",
    "pending",
    "running",
    "completed",
    "failed",
    "not_available",
    "no_public_email",
]


from app.schemas.verification import EmailVerificationRead


class LeadContactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lead_id: UUID
    email: str
    normalized_email: str
    contact_name: str | None = None
    role: str | None = None
    contact_type: str
    source: str
    source_url: str | None = None
    confidence: Confidence
    domain_match: bool
    is_primary: bool
    created_at: datetime
    updated_at: datetime
    verification: EmailVerificationRead | None = None
    verification_status: str | None = None


class ContactDiscoveryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lead_id: UUID
    status: str
    emails_found: int
    error_message: str | None = None
    discovered_at: datetime | None = None


class DiscoverContactsResponse(BaseModel):
    job_id: UUID
    status: str
    lead_ids: list[UUID]


class BatchDiscoverContactsRequest(BaseModel):
    lead_ids: list[UUID] | None = None
    website_exists: bool | None = True
    without_contacts: bool | None = True
    country: str | None = None
    industry: str | None = None
    limit: int = Field(default=50, ge=1, le=500)


class ContactJobStatusResponse(BaseModel):
    job_id: UUID
    status: str
    total: int
    processed: int
    succeeded: int
    failed: int
    progress: int
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
