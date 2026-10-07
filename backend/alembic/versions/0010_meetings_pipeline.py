"""Phase 10 Alembic migration — meetings + CRM pipeline.

Revision ID: 0010_meetings_pipeline
Revises: 0009_reply_intelligence
Create Date: 2026-08-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0010_meetings_pipeline"
down_revision = "0009_reply_intelligence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "leads",
        sa.Column("pipeline_stage", sa.String(length=64), nullable=False, server_default="new"),
    )
    op.create_index("ix_leads_pipeline_stage", "leads", ["pipeline_stage"])

    op.create_table(
        "meeting_types",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("buffer_before_minutes", sa.Integer(), nullable=False),
        sa.Column("buffer_after_minutes", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "availability_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_availability_rules_day_of_week", "availability_rules", ["day_of_week"])

    op.create_table(
        "availability_exceptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("end_time", sa.Time(), nullable=True),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_availability_exceptions_date", "availability_exceptions", ["date"])

    op.create_table(
        "meetings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id", ondelete="SET NULL"), nullable=True),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("lead_contacts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True),
        sa.Column("meeting_type_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("meeting_types.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("meeting_url", sa.String(length=512), nullable=True),
        sa.Column("external_event_id", sa.String(length=255), nullable=True),
        sa.Column("external_provider", sa.String(length=64), nullable=True),
        sa.Column("prospect_name", sa.String(length=255), nullable=True),
        sa.Column("prospect_email", sa.String(length=255), nullable=True),
        sa.Column("prospect_message", sa.Text(), nullable=True),
        sa.Column("outcome", sa.String(length=64), nullable=True),
        sa.Column("outcome_notes", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("booking_token_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_meetings_idempotency_key"),
    )
    op.create_index("ix_meetings_lead_id", "meetings", ["lead_id"])
    op.create_index("ix_meetings_contact_id", "meetings", ["contact_id"])
    op.create_index("ix_meetings_conversation_id", "meetings", ["conversation_id"])
    op.create_index("ix_meetings_campaign_id", "meetings", ["campaign_id"])
    op.create_index("ix_meetings_meeting_type_id", "meetings", ["meeting_type_id"])
    op.create_index("ix_meetings_status", "meetings", ["status"])
    op.create_index("ix_meetings_start_at", "meetings", ["start_at"])
    op.create_index("ix_meetings_prospect_email", "meetings", ["prospect_email"])
    op.create_index("ix_meetings_booking_token_id", "meetings", ["booking_token_id"])

    op.create_table(
        "meeting_reschedule_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("meeting_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("previous_start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("previous_end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("new_start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("new_end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_meeting_reschedule_history_meeting_id", "meeting_reschedule_history", ["meeting_id"])

    op.create_table(
        "booking_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=True),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("lead_contacts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("meeting_type_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("meeting_types.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("token", name="uq_booking_tokens_token"),
    )
    op.create_index("ix_booking_tokens_token", "booking_tokens", ["token"])
    op.create_index("ix_booking_tokens_lead_id", "booking_tokens", ["lead_id"])

    op.create_table(
        "lead_pipeline_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_stage", sa.String(length=64), nullable=True),
        sa.Column("to_stage", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_lead_pipeline_events_lead_id", "lead_pipeline_events", ["lead_id"])
    op.create_index("ix_lead_pipeline_events_to_stage", "lead_pipeline_events", ["to_stage"])
    op.create_index("ix_lead_pipeline_events_created_at", "lead_pipeline_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("lead_pipeline_events")
    op.drop_table("booking_tokens")
    op.drop_table("meeting_reschedule_history")
    op.drop_table("meetings")
    op.drop_table("availability_exceptions")
    op.drop_table("availability_rules")
    op.drop_table("meeting_types")
    op.drop_index("ix_leads_pipeline_stage", table_name="leads")
    op.drop_column("leads", "pipeline_stage")
