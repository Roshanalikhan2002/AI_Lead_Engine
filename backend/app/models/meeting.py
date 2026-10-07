"""Phase 10 — meetings."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Meeting(Base):
    __tablename__ = "meetings"
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key", name="uq_meetings_org_idempotency_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("leads.id", ondelete="SET NULL"), nullable=True, index=True
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("lead_contacts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True, index=True
    )
    meeting_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("meeting_types.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # requested | scheduled | confirmed | completed | cancelled | rescheduled | no_show
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="scheduled", index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    meeting_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    external_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prospect_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prospect_email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    prospect_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # interested | qualified | proposal_requested | not_interested | follow_up_required | won | lost | unknown
    outcome: Mapped[str | None] = mapped_column(String(64), nullable=True)
    outcome_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # uniqueness enforced as (organization_id, idempotency_key) via table args if present
    booking_token_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
