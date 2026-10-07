import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, DateTime, Float, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class GenerationJob(Base):
    __tablename__ = "generation_jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    country: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str | None] = mapped_column(String(128), nullable=True)
    city: Mapped[str] = mapped_column(String(128), nullable=False)
    industry: Mapped[str] = mapped_column(String(128), nullable=False)
    keywords: Mapped[str | None] = mapped_column(String(512), nullable=True)
    min_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_reviews: Mapped[int | None] = mapped_column(Integer, nullable=True)
    website_filter: Mapped[str] = mapped_column(String(32), nullable=False, default="any")
    requested_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    found_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    saved_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicates_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
