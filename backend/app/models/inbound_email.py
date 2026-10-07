"""Phase 9 — inbound email records."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class InboundEmail(Base):
    __tablename__ = "inbound_emails"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    thread_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    message_id_header: Mapped[str | None] = mapped_column(String(512), nullable=True)
    in_reply_to: Mapped[str | None] = mapped_column(String(512), nullable=True, index=True)
    references_header: Mapped[str | None] = mapped_column(Text, nullable=True)

    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("leads.id", ondelete="SET NULL"), nullable=True, index=True
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("lead_contacts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True
    )

    from_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    to_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")

    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # received | processing | processed | failed | ignored
    processing_status: Mapped[str] = mapped_column(String(32), nullable=False, default="received", index=True)
    # pending | classified | failed | skipped
    classification_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    match_confidence: Mapped[str | None] = mapped_column(String(16), nullable=True)  # high | medium | low | none
    match_method: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
