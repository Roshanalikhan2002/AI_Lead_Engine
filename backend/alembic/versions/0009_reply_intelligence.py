"""Phase 9 Alembic migration — reply intelligence.

Revision ID: 0009_reply_intelligence
Revises: 0008_campaigns
Create Date: 2026-08-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0009_reply_intelligence"
down_revision = "0008_campaigns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "email_messages",
        "outreach_draft_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    op.add_column(
        "email_messages",
        sa.Column("reply_suggestion_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_email_messages_reply_suggestion_id", "email_messages", ["reply_suggestion_id"])

    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id", ondelete="SET NULL"), nullable=True),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("lead_contacts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("provider_thread_id", sa.String(length=255), nullable=True),
        sa.Column("last_intent", sa.String(length=64), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_conversations_lead_id", "conversations", ["lead_id"])
    op.create_index("ix_conversations_contact_id", "conversations", ["contact_id"])
    op.create_index("ix_conversations_campaign_id", "conversations", ["campaign_id"])
    op.create_index("ix_conversations_status", "conversations", ["status"])
    op.create_index("ix_conversations_provider_thread_id", "conversations", ["provider_thread_id"])
    op.create_index("ix_conversations_last_intent", "conversations", ["last_intent"])
    op.create_index("ix_conversations_last_message_at", "conversations", ["last_message_at"])

    op.create_table(
        "inbound_emails",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("thread_id", sa.String(length=255), nullable=True),
        sa.Column("message_id_header", sa.String(length=512), nullable=True),
        sa.Column("in_reply_to", sa.String(length=512), nullable=True),
        sa.Column("references_header", sa.Text(), nullable=True),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id", ondelete="SET NULL"), nullable=True),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("lead_contacts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("from_email", sa.String(length=255), nullable=False),
        sa.Column("to_email", sa.String(length=255), nullable=True),
        sa.Column("subject", sa.String(length=500), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processing_status", sa.String(length=32), nullable=False),
        sa.Column("classification_status", sa.String(length=32), nullable=False),
        sa.Column("match_confidence", sa.String(length=16), nullable=True),
        sa.Column("match_method", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_inbound_emails_provider_message_id", "inbound_emails", ["provider_message_id"])
    op.create_index("ix_inbound_emails_thread_id", "inbound_emails", ["thread_id"])
    op.create_index("ix_inbound_emails_in_reply_to", "inbound_emails", ["in_reply_to"])
    op.create_index("ix_inbound_emails_lead_id", "inbound_emails", ["lead_id"])
    op.create_index("ix_inbound_emails_contact_id", "inbound_emails", ["contact_id"])
    op.create_index("ix_inbound_emails_conversation_id", "inbound_emails", ["conversation_id"])
    op.create_index("ix_inbound_emails_from_email", "inbound_emails", ["from_email"])
    op.create_index("ix_inbound_emails_processing_status", "inbound_emails", ["processing_status"])
    op.create_index("ix_inbound_emails_classification_status", "inbound_emails", ["classification_status"])

    op.create_table(
        "conversation_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("inbound_email_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inbound_emails.id", ondelete="SET NULL"), nullable=True),
        sa.Column("email_message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("email_messages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("message_type", sa.String(length=16), nullable=False),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("sender_email", sa.String(length=255), nullable=True),
        sa.Column("recipient_email", sa.String(length=255), nullable=True),
        sa.Column("subject", sa.String(length=500), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_conversation_messages_conversation_id", "conversation_messages", ["conversation_id"])
    op.create_index("ix_conversation_messages_direction", "conversation_messages", ["direction"])
    op.create_index("ix_conversation_messages_provider_message_id", "conversation_messages", ["provider_message_id"])

    op.create_table(
        "reply_classifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("inbound_email_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inbound_emails.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("intent", sa.String(length=64), nullable=False),
        sa.Column("intent_confidence", sa.Float(), nullable=True),
        sa.Column("sentiment", sa.String(length=32), nullable=False),
        sa.Column("sentiment_confidence", sa.Float(), nullable=True),
        sa.Column("urgency", sa.String(length=16), nullable=False),
        sa.Column("requires_human", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("model_version", sa.String(length=64), nullable=True),
        sa.Column("prompt_version", sa.String(length=32), nullable=True),
        sa.Column("input_hash", sa.String(length=64), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_reply_classifications_inbound_email_id", "reply_classifications", ["inbound_email_id"])
    op.create_index("ix_reply_classifications_conversation_id", "reply_classifications", ["conversation_id"])
    op.create_index("ix_reply_classifications_intent", "reply_classifications", ["intent"])
    op.create_index("ix_reply_classifications_input_hash", "reply_classifications", ["input_hash"])

    op.create_table(
        "reply_suggestions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("inbound_email_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("inbound_emails.id", ondelete="SET NULL"), nullable=True),
        sa.Column("subject", sa.String(length=500), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("model_version", sa.String(length=64), nullable=True),
        sa.Column("prompt_version", sa.String(length=32), nullable=True),
        sa.Column("input_hash", sa.String(length=64), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("email_message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("email_messages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_reply_suggestions_conversation_id", "reply_suggestions", ["conversation_id"])
    op.create_index("ix_reply_suggestions_inbound_email_id", "reply_suggestions", ["inbound_email_id"])
    op.create_index("ix_reply_suggestions_status", "reply_suggestions", ["status"])
    op.create_index("ix_reply_suggestions_input_hash", "reply_suggestions", ["input_hash"])


def downgrade() -> None:
    op.drop_table("reply_suggestions")
    op.drop_table("reply_classifications")
    op.drop_table("conversation_messages")
    op.drop_table("inbound_emails")
    op.drop_table("conversations")
    op.drop_index("ix_email_messages_reply_suggestion_id", table_name="email_messages")
    op.drop_column("email_messages", "reply_suggestion_id")
    op.alter_column(
        "email_messages",
        "outreach_draft_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
