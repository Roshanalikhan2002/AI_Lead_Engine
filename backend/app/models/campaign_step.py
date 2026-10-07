"""Phase 8 — campaign email sequence steps."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CampaignStep(Base):
    __tablename__ = "campaign_steps"
    __table_args__ = (UniqueConstraint("campaign_id", "step_number", name="uq_campaign_steps_number"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    # email (future: wait, condition, webhook, manual_task)
    type: Mapped[str] = mapped_column(String(32), nullable=False, default="email")
    # Delay AFTER previous step completes (0 for first step)
    delay_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Optional draft template; recipient uses enrolled draft if null
    outreach_draft_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("outreach_drafts.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
