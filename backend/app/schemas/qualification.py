from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


QualificationStatus = Literal[
    "qualified",
    "not_qualified",
    "insufficient_data",
    "error",
    "unconfigured",
]
Priority = Literal["hot", "warm", "cold", "unknown"]
Confidence = Literal["high", "medium", "low", "unknown"]


class AIQualificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lead_id: UUID
    status: QualificationStatus
    lead_score: int | None = None
    priority: Priority
    business_fit_score: int | None = None
    website_opportunity_score: int | None = None
    automation_opportunity_score: int | None = None
    contactability_score: int | None = None
    evidence_quality_score: int | None = None
    primary_service: str | None = None
    primary_opportunity_confidence: str | None = None
    primary_reason: str | None = None
    primary_evidence: list[str] | None = None
    additional_opportunities: list[dict[str, Any]] | None = None
    recommended_action: str | None = None
    personalization_insights: list[str] | None = None
    qualification_summary: str | None = None
    provider: str
    model: str | None = None
    model_version: str | None = None
    prompt_version: str | None = None
    input_hash: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class QualifyStartResponse(BaseModel):
    job_id: UUID | None = None
    status: str
    qualification: AIQualificationRead | None = None


class BatchQualifyRequest(BaseModel):
    lead_ids: list[UUID] | None = None
    only_unqualified: bool | None = True
    country: str | None = None
    industry: str | None = None
    website_analyzed: bool | None = None
    limit: int = Field(default=25, ge=1, le=200)


class QualificationJobStatusResponse(BaseModel):
    job_id: UUID
    status: str
    total: int
    processed: int
    qualified: int
    insufficient_data: int
    failed: int
    progress: int
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class QualificationStatsResponse(BaseModel):
    total_qualified: int
    hot_leads: int
    warm_leads: int
    cold_leads: int
    average_score: float | None = None
    top_opportunity: str | None = None
    top_industry: str | None = None
    has_real_data: bool
