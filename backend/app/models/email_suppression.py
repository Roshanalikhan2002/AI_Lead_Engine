"""Phase 7 — email suppression list (unsubscribe / bounce / complaint)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, DateTime, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EmailSuppression(Base):
    __tablename__ = "email_suppressions"
    __table_args__ = (UniqueConstraint("organization_id", "email", name="uq_email_suppressions_org_email"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    # unsubscribe | hard_bounce | manual_block | complaint
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="api")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
