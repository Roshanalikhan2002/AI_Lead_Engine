from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


AnalysisStatus = Literal["pending", "running", "completed", "failed", "not_available", "blocked"]
Confidence = Literal["high", "medium", "low"]


class WebsiteAnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lead_id: UUID
    website_url: str | None = None
    final_url: str | None = None
    http_status: int | None = None
    https_enabled: bool | None = None
    reachable: bool | None = None
    performance_score: int | None = None
    mobile_score: int | None = None
    seo_score: int | None = None
    accessibility_score: int | None = None
    website_score: int | None = None
    has_title: bool | None = None
    has_meta_description: bool | None = None
    has_h1: bool | None = None
    has_favicon: bool | None = None
    has_canonical: bool | None = None
    has_viewport: bool | None = None
    has_contact_form: bool | None = None
    has_booking: bool | None = None
    booking_evidence: list[Any] | None = None
    has_chatbot: bool | None = None
    chatbot_provider: str | None = None
    has_live_chat: bool | None = None
    has_phone: bool | None = None
    has_email: bool | None = None
    has_address: bool | None = None
    has_clear_cta: bool | None = None
    cta_evidence: list[Any] | None = None
    page_count: int | None = None
    load_time_ms: int | None = None
    page_size_bytes: int | None = None
    technology_detected: list[Any] | None = None
    seo_checks: dict[str, Any] | None = None
    score_reasons: list[Any] | None = None
    mobile_ready: bool | None = None
    analysis_status: AnalysisStatus
    error_message: str | None = None
    analyzed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class LeadOpportunityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lead_id: UUID
    service: str
    confidence: Confidence
    reason: str
    evidence: list[Any] | None = None
    source: str
    created_at: datetime


class AnalyzeStartResponse(BaseModel):
    job_id: UUID
    status: str
    lead_ids: list[UUID]


class BatchAnalyzeRequest(BaseModel):
    lead_ids: list[UUID] | None = None
    website_exists: bool | None = None
    not_analyzed: bool | None = True
    country: str | None = None
    industry: str | None = None
    limit: int = Field(default=50, ge=1, le=500)


class WebsiteJobStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
