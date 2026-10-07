from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


WebsiteFilter = Literal["any", "yes", "no"]
JobStatus = Literal["pending", "running", "completed", "failed", "cancelled"]


class GenerationCreateRequest(BaseModel):
    country: str = Field(..., min_length=2, max_length=64)
    state: str | None = Field(default=None, max_length=128)
    city: str = Field(..., min_length=1, max_length=128)
    industry: str = Field(..., min_length=1, max_length=128)
    keywords: str | None = Field(default=None, max_length=512)
    min_rating: float | None = Field(default=None, ge=0, le=5)
    min_reviews: int | None = Field(default=None, ge=0)
    website_filter: WebsiteFilter = "any"
    quantity: int = Field(..., ge=1, le=5000)

    @field_validator("country", "city", "industry")
    @classmethod
    def strip_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Value cannot be empty")
        return cleaned

    @field_validator("state", "keywords")
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class GenerationCreateResponse(BaseModel):
    job_id: UUID
    status: JobStatus


class GenerationStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: UUID
    status: JobStatus
    found: int
    processed: int
    saved: int
    duplicates_skipped: int
    target: int
    progress: int
    country: str
    state: str | None = None
    city: str
    industry: str
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
