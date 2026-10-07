"""Phase 5 — AI lead qualification result (1:1 with lead)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.database import Base

JSONType = JSON().with_variant(JSONB(), "postgresql")


class AIQualification(Base):
    __tablename__ = "ai_qualifications"
    __table_args__ = (UniqueConstraint("lead_id", name="uq_ai_qualifications_lead_id"),)

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

    # qualified | not_qualified | insufficient_data | error | unconfigured
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="unconfigured", index=True)
    lead_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # hot | warm | cold | unknown
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown", index=True)

    business_fit_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    website_opportunity_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    automation_opportunity_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    contactability_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence_quality_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    primary_service: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    primary_opportunity_confidence: Mapped[str | None] = mapped_column(String(16), nullable=True)
    primary_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_evidence: Mapped[list | None] = mapped_column(JSONType, nullable=True)
    additional_opportunities: Mapped[list | None] = mapped_column(JSONType, nullable=True)

    recommended_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    personalization_insights: Mapped[list | None] = mapped_column(JSONType, nullable=True)
    qualification_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="none")
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(32), nullable=True)

    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    error_message: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
