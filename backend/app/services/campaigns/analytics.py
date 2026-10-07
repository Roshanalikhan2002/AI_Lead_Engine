"""Campaign analytics from real EmailMessage / recipient data only."""

from __future__ import annotations

import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.campaign import Campaign
from app.models.campaign_recipient import CampaignRecipient
from app.models.campaign_step_execution import CampaignStepExecution
from app.models.email_message import EmailMessage


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 4)


def campaign_analytics(db: Session, campaign_id: uuid.UUID) -> dict:
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        return {}

    recipients = db.query(CampaignRecipient).filter(CampaignRecipient.campaign_id == campaign_id).all()
    total = len(recipients)
    by_status: dict[str, int] = {}
    for r in recipients:
        by_status[r.status] = by_status.get(r.status, 0) + 1

    # Sent / delivered / bounced from real EmailMessage rows linked via executions
    exec_msg_ids = [
        row[0]
        for row in db.query(CampaignStepExecution.email_message_id)
        .filter(
            CampaignStepExecution.campaign_id == campaign_id,
            CampaignStepExecution.email_message_id.isnot(None),
        )
        .all()
    ]

    sent = 0
    delivered = 0
    bounced = 0
    if exec_msg_ids:
        messages = db.query(EmailMessage).filter(EmailMessage.id.in_(exec_msg_ids)).all()
        for m in messages:
            if m.status in {"sent", "simulated", "delivered"}:
                sent += 1
            if m.status == "delivered":
                delivered += 1
            if m.status == "bounced":
                bounced += 1

    replied = by_status.get("replied", 0)
    unsubscribed = by_status.get("unsubscribed", 0)
    failed = by_status.get("failed", 0)
    completed = by_status.get("completed", 0)
    active = by_status.get("active", 0) + by_status.get("pending", 0) + by_status.get("paused", 0)

    return {
        "campaign_id": str(campaign_id),
        "status": campaign.status,
        "recipients": total,
        "active": active,
        "completed": completed,
        "sent": sent,
        "delivered": delivered,
        "bounced": bounced,
        "replied": replied,
        "unsubscribed": unsubscribed,
        "failed": failed,
        "delivery_rate": _rate(delivered, sent),
        "reply_rate": _rate(replied, delivered),
        "bounce_rate": _rate(bounced, sent),
        "unsubscribe_rate": _rate(unsubscribed, sent),
        "reply_detection_configured": False,
        "reply_detection_note": "Reply detection provider not configured",
        "has_send_data": sent > 0,
        "status_breakdown": by_status,
    }


def campaign_list_stats(db: Session, campaign_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict]:
    out: dict[uuid.UUID, dict] = {}
    for cid in campaign_ids:
        out[cid] = campaign_analytics(db, cid)
    return out
