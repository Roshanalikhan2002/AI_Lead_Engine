"""Phase 12 Alembic — multi-tenant auth.

Revision ID: 0012_multi_tenant_auth
Revises: 0011_production_hardening

Adds users/organizations/memberships and organization_id to tenant tables.
Creates a default development organization and backfills existing rows.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

revision = "0012_multi_tenant_auth"
down_revision = "0011_production_hardening"
branch_labels = None
depends_on = None

TENANT_TABLES = [
    "leads",
    "generation_jobs",
    "website_analyses",
    "website_analysis_jobs",
    "lead_opportunities",
    "contact_discoveries",
    "contact_discovery_jobs",
    "email_verifications",
    "email_verification_jobs",
    "ai_qualifications",
    "ai_qualification_jobs",
    "outreach_drafts",
    "outreach_generation_jobs",
    "email_messages",
    "email_suppressions",
    "campaigns",
    "campaign_steps",
    "campaign_recipients",
    "recipient_events",
    "campaign_step_executions",
    "conversations",
    "conversation_messages",
    "inbound_emails",
    "reply_classifications",
    "reply_suggestions",
    "meeting_types",
    "availability_rules",
    "availability_exceptions",
    "meetings",
    "meeting_reschedule_history",
    "booking_tokens",
    "lead_pipeline_events",
    "audit_logs",
    "job_records",
]


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("logo_url", sa.String(length=512), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="UTC"),
        sa.Column("default_currency", sa.String(length=8), nullable=False, server_default="USD"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("plan", sa.String(length=32), nullable=False, server_default="free"),
        sa.Column("branding_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"])
    op.create_index("ix_organizations_status", "organizations", ["status"])

    op.create_table(
        "organization_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("invited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_org_members_org_user"),
    )
    op.create_index("ix_organization_members_organization_id", "organization_members", ["organization_id"])
    op.create_index("ix_organization_members_user_id", "organization_members", ["user_id"])

    op.create_table(
        "organization_invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("invited_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("token_hash"),
    )

    op.create_table(
        "auth_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("refresh_token_hash"),
    )

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("token_hash"),
    )

    op.create_table(
        "organization_usage",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("leads_discovered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("website_analyses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("emails_discovered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("emails_verified", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ai_qualifications", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ai_generations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("emails_sent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("meetings_booked", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("organization_id", name="uq_organization_usage_org"),
    )

    default_org = str(uuid.uuid4())
    op.execute(
        sa.text(
            "INSERT INTO organizations (id, name, slug, timezone, default_currency, status, plan) "
            "VALUES (:id, 'Default Agency', 'default-agency', 'UTC', 'USD', 'active', 'free')"
        ).bindparams(id=default_org)
    )

    for table in TENANT_TABLES:
        nullable = table == "audit_logs"
        op.add_column(
            table,
            sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
        op.execute(sa.text(f"UPDATE {table} SET organization_id = :oid").bindparams(oid=default_org))
        if not nullable:
            op.alter_column(table, "organization_id", nullable=False)
        op.create_foreign_key(
            f"fk_{table}_organization_id",
            table,
            "organizations",
            ["organization_id"],
            ["id"],
            ondelete="CASCADE",
        )
        op.create_index(f"ix_{table}_organization_id", table, ["organization_id"])

    op.add_column(
        "audit_logs",
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_audit_logs_actor_user_id",
        "audit_logs",
        "users",
        ["actor_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Tenant-aware uniques
    op.drop_constraint("uq_leads_google_place_id", "leads", type_="unique")
    op.create_unique_constraint("uq_leads_org_google_place_id", "leads", ["organization_id", "google_place_id"])

    op.drop_constraint("uq_email_suppressions_email", "email_suppressions", type_="unique")
    op.create_unique_constraint(
        "uq_email_suppressions_org_email", "email_suppressions", ["organization_id", "email"]
    )

    op.drop_constraint("uq_email_messages_idempotency_key", "email_messages", type_="unique")
    op.create_unique_constraint(
        "uq_email_messages_org_idempotency_key",
        "email_messages",
        ["organization_id", "idempotency_key"],
    )

    op.drop_constraint("uq_job_records_idempotency_key", "job_records", type_="unique")
    op.create_unique_constraint(
        "uq_job_records_org_idempotency_key", "job_records", ["organization_id", "idempotency_key"]
    )

    # meetings idempotency was unique=True on column
    try:
        op.drop_constraint("meetings_idempotency_key_key", "meetings", type_="unique")
    except Exception:
        pass
    op.create_unique_constraint(
        "uq_meetings_org_idempotency_key", "meetings", ["organization_id", "idempotency_key"]
    )


def downgrade() -> None:
    # Non-destructive downgrade omitted for safety — restore from backup if needed.
    raise NotImplementedError("Downgrade of multi-tenant auth is not supported")
