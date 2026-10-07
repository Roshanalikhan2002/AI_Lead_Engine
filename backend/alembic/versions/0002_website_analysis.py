"""Phase 2 website analysis tables

Revision ID: 0002_website_analysis
Revises: 0001_initial
Create Date: 2026-08-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_website_analysis"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "website_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("website_url", sa.String(length=512), nullable=True),
        sa.Column("final_url", sa.String(length=512), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("https_enabled", sa.Boolean(), nullable=True),
        sa.Column("reachable", sa.Boolean(), nullable=True),
        sa.Column("performance_score", sa.Integer(), nullable=True),
        sa.Column("mobile_score", sa.Integer(), nullable=True),
        sa.Column("seo_score", sa.Integer(), nullable=True),
        sa.Column("accessibility_score", sa.Integer(), nullable=True),
        sa.Column("website_score", sa.Integer(), nullable=True),
        sa.Column("has_title", sa.Boolean(), nullable=True),
        sa.Column("has_meta_description", sa.Boolean(), nullable=True),
        sa.Column("has_h1", sa.Boolean(), nullable=True),
        sa.Column("has_favicon", sa.Boolean(), nullable=True),
        sa.Column("has_canonical", sa.Boolean(), nullable=True),
        sa.Column("has_viewport", sa.Boolean(), nullable=True),
        sa.Column("has_contact_form", sa.Boolean(), nullable=True),
        sa.Column("has_booking", sa.Boolean(), nullable=True),
        sa.Column("booking_evidence", sa.JSON(), nullable=True),
        sa.Column("has_chatbot", sa.Boolean(), nullable=True),
        sa.Column("chatbot_provider", sa.String(length=64), nullable=True),
        sa.Column("has_live_chat", sa.Boolean(), nullable=True),
        sa.Column("has_phone", sa.Boolean(), nullable=True),
        sa.Column("has_email", sa.Boolean(), nullable=True),
        sa.Column("has_address", sa.Boolean(), nullable=True),
        sa.Column("has_clear_cta", sa.Boolean(), nullable=True),
        sa.Column("cta_evidence", sa.JSON(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("load_time_ms", sa.Integer(), nullable=True),
        sa.Column("page_size_bytes", sa.Integer(), nullable=True),
        sa.Column("technology_detected", sa.JSON(), nullable=True),
        sa.Column("seo_checks", sa.JSON(), nullable=True),
        sa.Column("score_reasons", sa.JSON(), nullable=True),
        sa.Column("mobile_ready", sa.Boolean(), nullable=True),
        sa.Column("analysis_status", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("lead_id", name="uq_website_analyses_lead_id"),
    )
    op.create_index("ix_website_analyses_lead_id", "website_analyses", ["lead_id"])
    op.create_index("ix_website_analyses_analysis_status", "website_analyses", ["analysis_status"])

    op.create_table(
        "lead_opportunities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("service", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_lead_opportunities_lead_id", "lead_opportunities", ["lead_id"])
    op.create_index("ix_lead_opportunities_service", "lead_opportunities", ["service"])

    op.create_table(
        "website_analysis_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("lead_ids", sa.JSON(), nullable=True),
        sa.Column("filters", sa.JSON(), nullable=True),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("processed", sa.Integer(), nullable=False),
        sa.Column("succeeded", sa.Integer(), nullable=False),
        sa.Column("failed", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_website_analysis_jobs_status", "website_analysis_jobs", ["status"])


def downgrade() -> None:
    op.drop_table("website_analysis_jobs")
    op.drop_table("lead_opportunities")
    op.drop_table("website_analyses")
