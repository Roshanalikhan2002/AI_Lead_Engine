"""Phase 6 — personalized outreach email draft (no sending)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.database import Base

JSONType = JSON().with_variant(JSONB(), "postgresql")


class OutreachDraft(Base):
    __tablename__ = "outreach_drafts"

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
    contact_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("lead_contacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # draft | approved | rejected | edited | cancelled
    # "sent" reserved for Phase 7 — never set in Phase 6
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", index=True)

    selected_subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    alternative_subjects: Mapped[list | None] = mapped_column(JSONType, nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)

    service: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    personalization_points: Mapped[list | None] = mapped_column(JSONType, nullable=True)

    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="none")
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    error_message: Mapped[str | None] = mapped_column(String(255), nullable=True)
    generation_status: Mapped[str | None] = mapped_column(String(32), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
