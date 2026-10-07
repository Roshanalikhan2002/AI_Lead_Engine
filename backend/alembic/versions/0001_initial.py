"""initial leads and generation jobs

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "generation_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("country", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=128), nullable=True),
        sa.Column("city", sa.String(length=128), nullable=False),
        sa.Column("industry", sa.String(length=128), nullable=False),
        sa.Column("keywords", sa.String(length=512), nullable=True),
        sa.Column("min_rating", sa.Float(), nullable=True),
        sa.Column("min_reviews", sa.Integer(), nullable=True),
        sa.Column("website_filter", sa.String(length=32), nullable=False),
        sa.Column("requested_quantity", sa.Integer(), nullable=False),
        sa.Column("found_quantity", sa.Integer(), nullable=False),
        sa.Column("processed_quantity", sa.Integer(), nullable=False),
        sa.Column("saved_quantity", sa.Integer(), nullable=False),
        sa.Column("duplicates_skipped", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_generation_jobs_status", "generation_jobs", ["status"])

    op.create_table(
        "leads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("external_id", sa.String(length=128), nullable=True),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("industry", sa.String(length=128), nullable=True),
        sa.Column("country", sa.String(length=64), nullable=True),
        sa.Column("state", sa.String(length=128), nullable=True),
        sa.Column("city", sa.String(length=128), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("website", sa.String(length=512), nullable=True),
        sa.Column("google_place_id", sa.String(length=128), nullable=True),
        sa.Column("google_maps_url", sa.String(length=512), nullable=True),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("review_count", sa.Integer(), nullable=True),
        sa.Column("business_status", sa.String(length=64), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("normalized_phone", sa.String(length=64), nullable=True),
        sa.Column("normalized_domain", sa.String(length=255), nullable=True),
        sa.Column("generation_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("google_place_id", name="uq_leads_google_place_id"),
    )
    op.create_index("ix_leads_external_id", "leads", ["external_id"])
    op.create_index("ix_leads_country_city", "leads", ["country", "city"])
    op.create_index("ix_leads_industry", "leads", ["industry"])
    op.create_index("ix_leads_normalized_phone", "leads", ["normalized_phone"])
    op.create_index("ix_leads_normalized_domain", "leads", ["normalized_domain"])
    op.create_index("ix_leads_company_name", "leads", ["company_name"])
    op.create_index("ix_leads_generation_job_id", "leads", ["generation_job_id"])


def downgrade() -> None:
    op.drop_table("leads")
    op.drop_table("generation_jobs")
