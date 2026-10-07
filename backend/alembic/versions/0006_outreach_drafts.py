"""Phase 6 Alembic migration — outreach drafts (no sending).

Revision ID: 0006_outreach_drafts
Revises: 0005_ai_qualification
Create Date: 2026-08-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006_outreach_drafts"
down_revision = "0005_ai_qualification"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "outreach_drafts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "lead_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("leads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "contact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("lead_contacts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("selected_subject", sa.String(length=255), nullable=True),
        sa.Column("alternative_subjects", sa.JSON(), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("service", sa.String(length=64), nullable=True),
        sa.Column("personalization_points", sa.JSON(), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("model_version", sa.String(length=64), nullable=True),
        sa.Column("prompt_version", sa.String(length=32), nullable=True),
        sa.Column("input_hash", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.String(length=255), nullable=True),
        sa.Column("generation_status", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_outreach_drafts_lead_id", "outreach_drafts", ["lead_id"])
    op.create_index("ix_outreach_drafts_contact_id", "outreach_drafts", ["contact_id"])
    op.create_index("ix_outreach_drafts_status", "outreach_drafts", ["status"])
    op.create_index("ix_outreach_drafts_service", "outreach_drafts", ["service"])
    op.create_index("ix_outreach_drafts_input_hash", "outreach_drafts", ["input_hash"])

    op.create_table(
        "outreach_generation_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("lead_ids", sa.JSON(), nullable=True),
        sa.Column("filters", sa.JSON(), nullable=True),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("processed", sa.Integer(), nullable=False),
        sa.Column("generated_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_outreach_generation_jobs_status", "outreach_generation_jobs", ["status"])


def downgrade() -> None:
    op.drop_table("outreach_generation_jobs")
    op.drop_table("outreach_drafts")
