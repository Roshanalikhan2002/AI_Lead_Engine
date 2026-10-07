"""Phase 11 — standardized async job records (queue-swap ready)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, DateTime, Integer, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.database import Base

JSONType = JSON().with_variant(JSONB(), "postgresql")


class JobRecord(Base):
    __tablename__ = "job_records"
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key", name="uq_job_records_org_idempotency_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # lead_generation | website_analysis | contact_discovery | verification | qualification | outreach | campaign_tick | custom
    type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # pending | running | completed | failed | retrying | cancelled
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    payload: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
