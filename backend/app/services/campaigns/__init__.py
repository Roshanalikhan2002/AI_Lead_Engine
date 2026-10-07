"""Phase 8 campaign management services."""

from app.services.campaigns.enrollment import enroll_batch, enroll_recipient
from app.services.campaigns.events import apply_recipient_event, stop_recipients_for_email
from app.services.campaigns.execution import CampaignExecutionService, CampaignScheduler, execution_key_for
from app.services.campaigns.scheduler import compute_next_send_at
from app.services.campaigns.states import (
    CAMPAIGN_TRANSITIONS,
    RECIPIENT_TERMINAL,
    RECIPIENT_TRANSITIONS,
    assert_campaign_transition,
    assert_recipient_transition,
    maybe_complete_campaign,
)

__all__ = [
    "CAMPAIGN_TRANSITIONS",
    "RECIPIENT_TERMINAL",
    "RECIPIENT_TRANSITIONS",
    "CampaignExecutionService",
    "CampaignScheduler",
    "apply_recipient_event",
    "assert_campaign_transition",
    "assert_recipient_transition",
    "compute_next_send_at",
    "enroll_batch",
    "enroll_recipient",
    "execution_key_for",
    "maybe_complete_campaign",
    "stop_recipients_for_email",
]
