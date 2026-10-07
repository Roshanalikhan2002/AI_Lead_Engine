from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.contacts import LeadContactRead
from app.schemas.outreach import OutreachDraftRead
from app.schemas.qualification import AIQualificationRead
from app.schemas.sending import EmailMessageRead
from app.schemas.website import LeadOpportunityRead, WebsiteAnalysisRead


class LeadBase(BaseModel):
    company_name: str
    industry: str | None = None
    country: str | None = None
    state: str | None = None
    city: str | None = None
    address: str | None = None
    phone: str | None = None
    website: str | None = None
    google_place_id: str | None = None
    google_maps_url: str | None = None
    rating: float | None = None
    review_count: int | None = None
    business_status: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    source: str = "google_places"


class LeadRead(LeadBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    external_id: str | None = None
    normalized_phone: str | None = None
    normalized_domain: str | None = None
    generation_job_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
    website_analysis_status: str | None = None
    website_score: int | None = None
    website_analysis: WebsiteAnalysisRead | None = None
    opportunities: list[LeadOpportunityRead] = Field(default_factory=list)
    contact_discovery_status: str | None = None
    contact_email_count: int = 0
    contacts_verified_count: int = 0
    contacts_invalid_count: int = 0
    contacts_risky_count: int = 0
    contacts_unknown_count: int = 0
    contacts_unverified_count: int = 0
    contacts: list[LeadContactRead] = Field(default_factory=list)
    # Phase 5 — AI qualification (separate from website_score)
    qualification_status: str | None = None
    lead_score: int | None = None
    priority: str | None = None
    primary_service: str | None = None
    qualification: AIQualificationRead | None = None
    outreach_draft_status: str | None = None  # not_generated | draft | approved | rejected | edited
    outreach_ready: bool = False
    outreach_draft: OutreachDraftRead | None = None
    # Phase 7 — sending (from latest EmailMessage)
    sending_status: str | None = None  # not_sent | simulated | sent | delivered | failed | bounced | blocked
    latest_email_message: EmailMessageRead | None = None


class LeadListResponse(BaseModel):
    items: list[LeadRead]
    total: int
    page: int
    limit: int
    pages: int
