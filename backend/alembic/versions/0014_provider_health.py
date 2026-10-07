"""Phase 14 Alembic — provider health + operation logs.

Revision ID: 0014_provider_health
Revises: 0013_billing
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0014_provider_health"
down_revision = "0013_billing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_health_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False, server_default="unavailable"),
        sa.Column("configured", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("healthy", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("live_tested", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("degraded", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.Column("last_error_summary", sa.String(length=500), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("organization_id", "provider", name="uq_provider_health_org_provider"),
    )
    op.create_index("ix_provider_health_states_organization_id", "provider_health_states", ["organization_id"])
    op.create_index("ix_provider_health_states_provider", "provider_health_states", ["provider"])

    op.create_table(
        "provider_operation_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("operation", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("provider_request_id", sa.String(length=128), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_summary", sa.String(length=500), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_provider_operation_logs_organization_id", "provider_operation_logs", ["organization_id"])
    op.create_index("ix_provider_operation_logs_provider", "provider_operation_logs", ["provider"])
    op.create_index("ix_provider_operation_logs_status", "provider_operation_logs", ["status"])
    op.create_index("ix_provider_operation_logs_created_at", "provider_operation_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("provider_operation_logs")
    op.drop_table("provider_health_states")
