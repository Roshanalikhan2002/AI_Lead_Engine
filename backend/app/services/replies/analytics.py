"""Reply analytics from real conversation data only."""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.models.inbound_email import InboundEmail
from app.models.reply_classification import ReplyClassification


def _rate(n: int, d: int) -> float | None:
    if d <= 0:
        return None
    return round(n / d, 4)


def reply_analytics(db: Session) -> dict:
    total_replies = db.query(func.count(InboundEmail.id)).scalar() or 0
    classified = (
        db.query(ReplyClassification.intent, func.count(ReplyClassification.id))
        .group_by(ReplyClassification.intent)
        .all()
    )
    by_intent = {intent: count for intent, count in classified}

    # Prefer latest classification per inbound — approximate via totals is OK for dashboard
    interested = by_intent.get("interested", 0)
    meetings = by_intent.get("meeting_request", 0)
    questions = by_intent.get("question", 0) + by_intent.get("pricing_question", 0) + by_intent.get(
        "needs_information", 0
    )
    not_interested = by_intent.get("not_interested", 0)
    unsubscribes = by_intent.get("unsubscribe", 0)
    unknown = by_intent.get("unknown", 0)

    conversations = db.query(func.count(Conversation.id)).scalar() or 0
    has_real = total_replies > 0

    # Reply rate needs outbound sends as denominator — use EmailMessage when available
    from app.models.email_message import EmailMessage

    outbound = (
        db.query(func.count(EmailMessage.id))
        .filter(EmailMessage.status.in_(["sent", "simulated", "delivered"]))
        .scalar()
        or 0
    )

    return {
        "total_replies": total_replies,
        "conversations": conversations,
        "interested": interested,
        "meeting_requests": meetings,
        "questions": questions,
        "not_interested": not_interested,
        "unsubscribes": unsubscribes,
        "unknown": unknown,
        "reply_rate": _rate(total_replies, outbound),
        "interest_rate": _rate(interested, total_replies),
        "meeting_request_rate": _rate(meetings, total_replies),
        "unsubscribe_rate": _rate(unsubscribes, total_replies),
        "has_real_data": has_real,
        "reply_tracking_live": False,
        "note": "Reply tracking uses configured inbound/webhook events only; not live-tested by default.",
    }
