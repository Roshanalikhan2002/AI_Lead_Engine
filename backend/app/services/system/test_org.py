"""Isolated Provider Test Organization — never mixes with customer analytics/usage."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.auth import Organization, OrganizationMember, User
from app.core.tenant import hash_password
from app.services.auth.service import ensure_usage
from app.services.billing.service import ensure_free_subscription

PROVIDER_TEST_ORG_SLUG = "provider-test"
PROVIDER_TEST_ORG_NAME = "Provider Test Organization"
PROVIDER_TEST_LEAD_SOURCE = "provider_test"
PROVIDER_TEST_OWNER_EMAIL = "provider-test-owner@leadflow.local"


def is_provider_test_org(db: Session, organization_id: uuid.UUID | None) -> bool:
    if not organization_id:
        return False
    org = db.get(Organization, organization_id)
    return bool(org and org.slug == PROVIDER_TEST_ORG_SLUG)


def is_provider_test_lead_source(source: str | None) -> bool:
    return (source or "").strip().lower() == PROVIDER_TEST_LEAD_SOURCE


def ensure_provider_test_organization(db: Session) -> Organization:
    """Get or create the isolated provider-test org (idempotent)."""
    existing = db.query(Organization).filter(Organization.slug == PROVIDER_TEST_ORG_SLUG).one_or_none()
    if existing:
        return existing

    owner = db.query(User).filter(User.email == PROVIDER_TEST_OWNER_EMAIL).one_or_none()
    if not owner:
        owner = User(
            email=PROVIDER_TEST_OWNER_EMAIL,
            password_hash=hash_password(uuid.uuid4().hex + "Aa1!"),
            first_name="Provider",
            last_name="Test",
            is_active=True,
            is_verified=True,
        )
        db.add(owner)
        db.flush()

    org = Organization(
        name=PROVIDER_TEST_ORG_NAME,
        slug=PROVIDER_TEST_ORG_SLUG,
        timezone="UTC",
        default_currency="USD",
        status="active",
        plan="free",
        branding_json={"provider_test": True, "exclude_from_analytics": True},
    )
    db.add(org)
    db.flush()
    db.add(
        OrganizationMember(
            organization_id=org.id,
            user_id=owner.id,
            role="owner",
            status="active",
        )
    )
    ensure_usage(db, org.id)
    ensure_free_subscription(db, org.id)
    db.commit()
    db.refresh(org)
    return org
