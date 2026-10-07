"""Phase 13 Alembic — SaaS billing tables.

Revision ID: 0013_billing
Revises: 0012_multi_tenant_auth
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0013_billing"
down_revision = "0012_multi_tenant_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "billing_customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False, server_default="unconfigured"),
        sa.Column("external_customer_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("organization_id", "provider", name="uq_billing_customers_org_provider"),
    )
    op.create_index("ix_billing_customers_organization_id", "billing_customers", ["organization_id"])
    op.create_index("ix_billing_customers_external_customer_id", "billing_customers", ["external_customer_id"])

    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False, server_default="unconfigured"),
        sa.Column("external_customer_id", sa.String(length=255), nullable=True),
        sa.Column("external_subscription_id", sa.String(length=255), nullable=True),
        sa.Column("plan", sa.String(length=32), nullable=False, server_default="free"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("billing_interval", sa.String(length=16), nullable=False, server_default="month"),
        sa.Column("trial_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trial_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("grace_period_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_subscriptions_organization_id", "subscriptions", ["organization_id"])
    op.create_index("ix_subscriptions_external_subscription_id", "subscriptions", ["external_subscription_id"])
    op.create_index("ix_subscriptions_plan", "subscriptions", ["plan"])
    op.create_index("ix_subscriptions_status", "subscriptions", ["status"])

    op.create_table(
        "usage_periods",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("leads_discovered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("website_analyses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("emails_discovered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("emails_verified", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ai_qualifications", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ai_generations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ai_reply_classifications", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ai_reply_suggestions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("emails_sent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("meetings_booked", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("organization_id", "period_start", "period_end", name="uq_usage_periods_org_window"),
    )
    op.create_index("ix_usage_periods_organization_id", "usage_periods", ["organization_id"])

    op.create_table(
        "billing_webhook_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("external_event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("processed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.String(length=500), nullable=True),
        sa.Column("payload_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("provider", "external_event_id", name="uq_billing_webhook_provider_event"),
    )
    op.create_index("ix_billing_webhook_events_organization_id", "billing_webhook_events", ["organization_id"])
    op.create_index("ix_billing_webhook_events_provider", "billing_webhook_events", ["provider"])


def downgrade() -> None:
    op.drop_table("billing_webhook_events")
    op.drop_table("usage_periods")
    op.drop_table("subscriptions")
    op.drop_table("billing_customers")
