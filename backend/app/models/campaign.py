"""Phase 8 — outreach campaigns."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Boolean, DateTime, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # draft | active | paused | completed | cancelled
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", index=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    daily_send_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    hourly_send_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    send_start_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=9)
    send_end_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=17)
    send_on_weekends: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
