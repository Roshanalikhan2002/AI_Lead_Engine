"""Phase 10 — date-specific availability exceptions."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time

from sqlalchemy import ForeignKey, Date, DateTime, String, Text, Time, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AvailabilityException(Base):
    __tablename__ = "availability_exceptions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    # blocked | available
    type: Mapped[str] = mapped_column(String(32), nullable=False, default="blocked")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
