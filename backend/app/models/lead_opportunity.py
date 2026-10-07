import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.database import Base

JSONType = JSON().with_variant(JSONB(), "postgresql")


class LeadOpportunity(Base):
    __tablename__ = "lead_opportunities"

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
    service: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False)  # high | medium | low
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[list | None] = mapped_column(JSONType, nullable=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="website_analysis")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
