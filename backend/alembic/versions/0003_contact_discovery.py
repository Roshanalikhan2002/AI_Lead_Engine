"""Phase 3 contact discovery tables

Revision ID: 0003_contact_discovery
Revises: 0002_website_analysis
Create Date: 2026-08-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_contact_discovery"
down_revision = "0002_website_analysis"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lead_contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("normalized_email", sa.String(length=320), nullable=False),
        sa.Column("contact_name", sa.String(length=255), nullable=True),
        sa.Column("role", sa.String(length=128), nullable=True),
        sa.Column("contact_type", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_url", sa.String(length=512), nullable=True),
        sa.Column("confidence", sa.String(length=16), nullable=False),
        sa.Column("domain_match", sa.Boolean(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("lead_id", "normalized_email", name="uq_lead_contacts_lead_email"),
    )
    op.create_index("ix_lead_contacts_lead_id", "lead_contacts", ["lead_id"])
    op.create_index("ix_lead_contacts_normalized_email", "lead_contacts", ["normalized_email"])
    op.create_index("ix_lead_contacts_contact_type", "lead_contacts", ["contact_type"])

    op.create_table(
        "contact_discoveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("emails_found", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("lead_id", name="uq_contact_discoveries_lead_id"),
    )
    op.create_index("ix_contact_discoveries_lead_id", "contact_discoveries", ["lead_id"])
    op.create_index("ix_contact_discoveries_status", "contact_discoveries", ["status"])

    op.create_table(
        "contact_discovery_jobs",
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
    op.create_index("ix_contact_discovery_jobs_status", "contact_discovery_jobs", ["status"])


def downgrade() -> None:
    op.drop_table("contact_discovery_jobs")
    op.drop_table("contact_discoveries")
    op.drop_table("lead_contacts")
