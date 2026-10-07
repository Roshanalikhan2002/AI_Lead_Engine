"""Phase 8 Alembic migration — campaigns + follow-ups.

Revision ID: 0008_campaigns
Revises: 0007_email_sending
Create Date: 2026-08-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0008_campaigns"
down_revision = "0007_email_sending"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("daily_send_limit", sa.Integer(), nullable=False),
        sa.Column("hourly_send_limit", sa.Integer(), nullable=False),
        sa.Column("send_start_hour", sa.Integer(), nullable=False),
        sa.Column("send_end_hour", sa.Integer(), nullable=False),
        sa.Column("send_on_weekends", sa.Boolean(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_campaigns_status", "campaigns", ["status"])

    op.create_table(
        "campaign_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("delay_minutes", sa.Integer(), nullable=False),
        sa.Column("outreach_draft_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("outreach_drafts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("campaign_id", "step_number", name="uq_campaign_steps_number"),
    )
    op.create_index("ix_campaign_steps_campaign_id", "campaign_steps", ["campaign_id"])

    op.create_table(
        "campaign_recipients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("lead_contacts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("outreach_draft_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("outreach_drafts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("current_step", sa.Integer(), nullable=False),
        sa.Column("next_action_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("enrolled_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=255), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("campaign_id", "contact_id", name="uq_campaign_recipients_contact"),
    )
    op.create_index("ix_campaign_recipients_campaign_id", "campaign_recipients", ["campaign_id"])
    op.create_index("ix_campaign_recipients_lead_id", "campaign_recipients", ["lead_id"])
    op.create_index("ix_campaign_recipients_contact_id", "campaign_recipients", ["contact_id"])
    op.create_index("ix_campaign_recipients_status", "campaign_recipients", ["status"])
    op.create_index("ix_campaign_recipients_next_action_at", "campaign_recipients", ["next_action_at"])

    op.create_table(
        "recipient_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "campaign_recipient_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campaign_recipients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("provider_event_id", sa.String(length=255), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_recipient_events_campaign_recipient_id", "recipient_events", ["campaign_recipient_id"])
    op.create_index("ix_recipient_events_event_type", "recipient_events", ["event_type"])

    op.create_table(
        "campaign_step_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "campaign_recipient_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campaign_recipients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column("execution_key", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("email_message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("email_messages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("error_message", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("execution_key", name="uq_campaign_step_executions_key"),
    )
    op.create_index("ix_campaign_step_executions_campaign_id", "campaign_step_executions", ["campaign_id"])
    op.create_index("ix_campaign_step_executions_campaign_recipient_id", "campaign_step_executions", ["campaign_recipient_id"])


def downgrade() -> None:
    op.drop_table("campaign_step_executions")
    op.drop_table("recipient_events")
    op.drop_table("campaign_recipients")
    op.drop_table("campaign_steps")
    op.drop_table("campaigns")
