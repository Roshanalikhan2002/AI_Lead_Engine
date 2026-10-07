"""Phase 4 email verification tables

Revision ID: 0004_email_verification
Revises: 0003_contact_discovery
Create Date: 2026-08-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_email_verification"
down_revision = "0003_contact_discovery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_verifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "lead_contact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("lead_contacts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_summary", sa.String(length=255), nullable=True),
        sa.Column("is_valid", sa.Boolean(), nullable=True),
        sa.Column("is_risky", sa.Boolean(), nullable=True),
        sa.Column("is_disposable", sa.Boolean(), nullable=True),
        sa.Column("is_role_based", sa.Boolean(), nullable=True),
        sa.Column("is_free_provider", sa.Boolean(), nullable=True),
        sa.Column("mx_found", sa.Boolean(), nullable=True),
        sa.Column("domain", sa.String(length=255), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("lead_contact_id", name="uq_email_verifications_contact"),
    )
    op.create_index("ix_email_verifications_lead_contact_id", "email_verifications", ["lead_contact_id"])
    op.create_index("ix_email_verifications_status", "email_verifications", ["status"])

    op.create_table(
        "email_verification_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("contact_ids", sa.JSON(), nullable=True),
        sa.Column("filters", sa.JSON(), nullable=True),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("processed", sa.Integer(), nullable=False),
        sa.Column("valid_count", sa.Integer(), nullable=False),
        sa.Column("invalid_count", sa.Integer(), nullable=False),
        sa.Column("risky_count", sa.Integer(), nullable=False),
        sa.Column("unknown_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_email_verification_jobs_status", "email_verification_jobs", ["status"])


def downgrade() -> None:
    op.drop_table("email_verification_jobs")
    op.drop_table("email_verifications")
