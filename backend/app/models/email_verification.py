import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.database import Base

JSONType = JSON().with_variant(JSONB(), "postgresql")


class EmailVerification(Base):
    __tablename__ = "email_verifications"
    __table_args__ = (UniqueConstraint("lead_contact_id", name="uq_email_verifications_contact"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lead_contact_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("lead_contacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # pending | valid | invalid | risky | unknown | blocked | error
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="none")
    # Sanitized summary only — never store full secrets; keep minimal diagnostics
    provider_summary: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_valid: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_risky: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_disposable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_role_based: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_free_provider: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    mx_found: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
