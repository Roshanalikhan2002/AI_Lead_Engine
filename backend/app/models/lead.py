import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, DateTime, Float, Index, Integer, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (
        UniqueConstraint("organization_id", "google_place_id", name="uq_leads_org_google_place_id"),
        Index("ix_leads_country_city", "country", "city"),
        Index("ix_leads_industry", "industry"),
        Index("ix_leads_normalized_phone", "normalized_phone"),
        Index("ix_leads_normalized_domain", "normalized_domain"),
        Index("ix_leads_company_name", "company_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    industry: Mapped[str | None] = mapped_column(String(128), nullable=True)
    country: Mapped[str | None] = mapped_column(String(64), nullable=True)
    state: Mapped[str | None] = mapped_column(String(128), nullable=True)
    city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    website: Mapped[str | None] = mapped_column(String(512), nullable=True)
    google_place_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    google_maps_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    business_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="google_places")
    normalized_phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    normalized_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    generation_job_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    # new | qualified | contacted | replied | meeting_requested | meeting_scheduled | meeting_completed | proposal | won | lost
    pipeline_stage: Mapped[str] = mapped_column(String(64), nullable=False, default="new", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
