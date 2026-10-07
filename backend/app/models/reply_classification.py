"""Phase 9 — AI reply classification results."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.database import Base

JSONType = JSON().with_variant(JSONB(), "postgresql")


class ReplyClassification(Base):
    __tablename__ = "reply_classifications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    inbound_email_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("inbound_emails.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    intent: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown", index=True)
    intent_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    sentiment: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    sentiment_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    urgency: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    requires_human: Mapped[bool] = mapped_column(default=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[list | None] = mapped_column(JSONType, nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="none")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
