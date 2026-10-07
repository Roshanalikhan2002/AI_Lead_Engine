"""Phase 7 Alembic migration — email messages + suppressions.

Revision ID: 0007_email_sending
Revises: 0006_outreach_drafts
Create Date: 2026-08-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007_email_sending"
down_revision = "0006_outreach_drafts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_suppressions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("reason", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("email", name="uq_email_suppressions_email"),
    )
    op.create_index("ix_email_suppressions_email", "email_suppressions", ["email"])

    op.create_table(
        "email_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "contact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("lead_contacts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "outreach_draft_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("outreach_drafts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sender_email", sa.String(length=255), nullable=False),
        sa.Column("sender_name", sa.String(length=255), nullable=False),
        sa.Column("recipient_email", sa.String(length=255), nullable=False),
        sa.Column("recipient_name", sa.String(length=255), nullable=True),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("test_mode", sa.Boolean(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.String(length=255), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_email_messages_idempotency_key"),
    )
    op.create_index("ix_email_messages_lead_id", "email_messages", ["lead_id"])
    op.create_index("ix_email_messages_contact_id", "email_messages", ["contact_id"])
    op.create_index("ix_email_messages_outreach_draft_id", "email_messages", ["outreach_draft_id"])
    op.create_index("ix_email_messages_recipient_email", "email_messages", ["recipient_email"])
    op.create_index("ix_email_messages_provider_message_id", "email_messages", ["provider_message_id"])
    op.create_index("ix_email_messages_status", "email_messages", ["status"])


def downgrade() -> None:
    op.drop_table("email_messages")
    op.drop_table("email_suppressions")
