"""Phase 5 Alembic migration — AI qualification tables.

Revision ID: 0005_ai_qualification
Revises: 0004_email_verification
Create Date: 2026-08-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005_ai_qualification"
down_revision = "0004_email_verification"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_qualifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "lead_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("leads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("lead_score", sa.Integer(), nullable=True),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("business_fit_score", sa.Integer(), nullable=True),
        sa.Column("website_opportunity_score", sa.Integer(), nullable=True),
        sa.Column("automation_opportunity_score", sa.Integer(), nullable=True),
        sa.Column("contactability_score", sa.Integer(), nullable=True),
        sa.Column("evidence_quality_score", sa.Integer(), nullable=True),
        sa.Column("primary_service", sa.String(length=64), nullable=True),
        sa.Column("primary_opportunity_confidence", sa.String(length=16), nullable=True),
        sa.Column("primary_reason", sa.Text(), nullable=True),
        sa.Column("primary_evidence", sa.JSON(), nullable=True),
        sa.Column("additional_opportunities", sa.JSON(), nullable=True),
        sa.Column("recommended_action", sa.Text(), nullable=True),
        sa.Column("personalization_insights", sa.JSON(), nullable=True),
        sa.Column("qualification_summary", sa.Text(), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("model_version", sa.String(length=64), nullable=True),
        sa.Column("prompt_version", sa.String(length=32), nullable=True),
        sa.Column("input_hash", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("lead_id", name="uq_ai_qualifications_lead_id"),
    )
    op.create_index("ix_ai_qualifications_lead_id", "ai_qualifications", ["lead_id"])
    op.create_index("ix_ai_qualifications_status", "ai_qualifications", ["status"])
    op.create_index("ix_ai_qualifications_priority", "ai_qualifications", ["priority"])
    op.create_index("ix_ai_qualifications_primary_service", "ai_qualifications", ["primary_service"])
    op.create_index("ix_ai_qualifications_input_hash", "ai_qualifications", ["input_hash"])

    op.create_table(
        "ai_qualification_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("lead_ids", sa.JSON(), nullable=True),
        sa.Column("filters", sa.JSON(), nullable=True),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("processed", sa.Integer(), nullable=False),
        sa.Column("qualified_count", sa.Integer(), nullable=False),
        sa.Column("insufficient_data_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ai_qualification_jobs_status", "ai_qualification_jobs", ["status"])


def downgrade() -> None:
    op.drop_table("ai_qualification_jobs")
    op.drop_table("ai_qualifications")
