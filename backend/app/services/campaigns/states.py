"""Explicit campaign / recipient state machines."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.campaign import Campaign
from app.models.campaign_recipient import CampaignRecipient

CAMPAIGN_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"active", "cancelled"},
    "active": {"paused", "completed", "cancelled"},
    "paused": {"active", "cancelled", "completed"},
    "completed": set(),
    "cancelled": set(),
}

RECIPIENT_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"active", "cancelled", "failed"},
    "active": {
        "completed",
        "paused",
        "replied",
        "bounced",
        "unsubscribed",
        "failed",
        "cancelled",
    },
    "paused": {"active", "cancelled", "replied", "bounced", "unsubscribed", "failed"},
    "completed": set(),
    "replied": set(),
    "bounced": set(),
    "unsubscribed": set(),
    "failed": set(),
    "cancelled": set(),
}

RECIPIENT_TERMINAL = frozenset(
    {"completed", "replied", "bounced", "unsubscribed", "failed", "cancelled"}
)


class CampaignStateError(ValueError):
    def __init__(self, message: str, *, code: str = "invalid_transition"):
        super().__init__(message)
        self.code = code


def assert_campaign_transition(current: str, target: str) -> None:
    allowed = CAMPAIGN_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise CampaignStateError(
            f"Cannot transition campaign from {current} to {target}",
            code="invalid_campaign_transition",
        )


def assert_recipient_transition(current: str, target: str) -> None:
    allowed = RECIPIENT_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise CampaignStateError(
            f"Cannot transition recipient from {current} to {target}",
            code="invalid_recipient_transition",
        )


def maybe_complete_campaign(db: Session, campaign: Campaign) -> bool:
    """Mark campaign completed when every recipient is terminal and at least one exists."""
    recipients = (
        db.query(CampaignRecipient).filter(CampaignRecipient.campaign_id == campaign.id).all()
    )
    if not recipients:
        return False
    if any(r.status not in RECIPIENT_TERMINAL for r in recipients):
        return False
    if campaign.status in {"completed", "cancelled"}:
        return False
    if campaign.status not in {"active", "paused"}:
        return False
    assert_campaign_transition(campaign.status, "completed")
    campaign.status = "completed"
    campaign.updated_at = datetime.now(timezone.utc)
    db.commit()
    return True
