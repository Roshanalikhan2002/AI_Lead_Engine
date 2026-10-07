import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.database import Base

# JSON that works on PostgreSQL and SQLite
JSONType = JSON().with_variant(JSONB(), "postgresql")


class WebsiteAnalysis(Base):
    __tablename__ = "website_analyses"
    __table_args__ = (UniqueConstraint("lead_id", name="uq_website_analyses_lead_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    website_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    final_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    https_enabled: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    reachable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    performance_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mobile_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    seo_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    accessibility_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    website_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    has_title: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_meta_description: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_h1: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_favicon: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_canonical: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_viewport: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    has_contact_form: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_booking: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    booking_evidence: Mapped[list | None] = mapped_column(JSONType, nullable=True)
    has_chatbot: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    chatbot_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    has_live_chat: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    has_phone: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_email: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_address: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_clear_cta: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    cta_evidence: Mapped[list | None] = mapped_column(JSONType, nullable=True)

    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    load_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    technology_detected: Mapped[list | None] = mapped_column(JSONType, nullable=True)
    seo_checks: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    score_reasons: Mapped[list | None] = mapped_column(JSONType, nullable=True)
    mobile_ready: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    analysis_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
