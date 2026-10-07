"""Meeting / pipeline analytics — real data only."""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.lead import Lead
from app.models.meeting import Meeting
from app.models.inbound_email import InboundEmail
from app.models.reply_classification import ReplyClassification


def _rate(n: int, d: int) -> float | None:
    if d <= 0:
        return None
    return round(n / d, 4)


def pipeline_stats(db: Session) -> dict:
    from app.models.auth import Organization
    from app.services.system.test_org import PROVIDER_TEST_LEAD_SOURCE, PROVIDER_TEST_ORG_SLUG

    test_org_ids = [
        r[0]
        for r in db.query(Organization.id).filter(Organization.slug == PROVIDER_TEST_ORG_SLUG).all()
    ]
    stage_q = db.query(Lead.pipeline_stage, func.count(Lead.id)).filter(
        Lead.source != PROVIDER_TEST_LEAD_SOURCE
    )
    if test_org_ids:
        stage_q = stage_q.filter(~Lead.organization_id.in_(test_org_ids))
    rows = stage_q.group_by(Lead.pipeline_stage).all()
    by_stage = {s: c for s, c in rows}
    total = sum(by_stage.values())
    qualified = by_stage.get("qualified", 0) + sum(
        by_stage.get(s, 0)
        for s in (
            "contacted",
            "replied",
            "meeting_requested",
            "meeting_scheduled",
            "meeting_completed",
            "proposal",
            "won",
        )
    )
    contacted = sum(
        by_stage.get(s, 0)
        for s in (
            "contacted",
            "replied",
            "meeting_requested",
            "meeting_scheduled",
            "meeting_completed",
            "proposal",
            "won",
            "lost",
        )
    )
    replied = sum(
        by_stage.get(s, 0)
        for s in (
            "replied",
            "meeting_requested",
            "meeting_scheduled",
            "meeting_completed",
            "proposal",
            "won",
        )
    )
    meeting_req = sum(
        by_stage.get(s, 0)
        for s in ("meeting_requested", "meeting_scheduled", "meeting_completed", "proposal", "won")
    )
    scheduled = sum(
        by_stage.get(s, 0) for s in ("meeting_scheduled", "meeting_completed", "proposal", "won")
    )
    completed = sum(by_stage.get(s, 0) for s in ("meeting_completed", "proposal", "won"))
    proposals = sum(by_stage.get(s, 0) for s in ("proposal", "won"))
    won = by_stage.get("won", 0)
    lost = by_stage.get("lost", 0)

    meetings_scheduled = (
        db.query(func.count(Meeting.id))
        .filter(Meeting.status.in_(["scheduled", "confirmed", "rescheduled", "completed", "no_show"]))
        .scalar()
        or 0
    )
    meetings_completed = (
        db.query(func.count(Meeting.id)).filter(Meeting.status == "completed").scalar() or 0
    )
    meeting_requests_cls = (
        db.query(func.count(ReplyClassification.id))
        .filter(ReplyClassification.intent == "meeting_request")
        .scalar()
        or 0
    )
    replies = db.query(func.count(InboundEmail.id)).scalar() or 0

    return {
        "total_leads": total,
        "by_stage": by_stage,
        "qualified": by_stage.get("qualified", 0),
        "contacted": by_stage.get("contacted", 0),
        "replied": by_stage.get("replied", 0),
        "meeting_requested": by_stage.get("meeting_requested", 0),
        "meeting_scheduled": by_stage.get("meeting_scheduled", 0),
        "meeting_completed": by_stage.get("meeting_completed", 0),
        "proposal": by_stage.get("proposal", 0),
        "won": won,
        "lost": lost,
        "meetings_scheduled_count": meetings_scheduled,
        "meetings_completed_count": meetings_completed,
        "meeting_request_classifications": meeting_requests_cls,
        "replies": replies,
        "qualification_rate": _rate(qualified, total),
        "reply_rate": _rate(replies, contacted) if contacted else _rate(replies, total),
        "meeting_request_rate": _rate(meeting_requests_cls, replies),
        "booking_rate": _rate(meetings_scheduled, meeting_req or meeting_requests_cls),
        "meeting_completion_rate": _rate(meetings_completed, meetings_scheduled),
        "proposal_rate": _rate(proposals, completed or meetings_completed),
        "win_rate": _rate(won, won + lost),
        "has_real_data": total > 0 or meetings_scheduled > 0 or replies > 0,
        "calendar_live": False,
        "revenue": None,
        "note": "No revenue metrics. Calendar not live-connected by default. Provider-test leads excluded.",
    }


def meeting_list_stats(db: Session) -> dict:
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    upcoming = (
        db.query(func.count(Meeting.id))
        .filter(Meeting.status.in_(["scheduled", "confirmed", "rescheduled"]), Meeting.start_at >= now)
        .scalar()
        or 0
    )
    return {
        "upcoming": upcoming,
        "completed": db.query(func.count(Meeting.id)).filter(Meeting.status == "completed").scalar() or 0,
        "cancelled": db.query(func.count(Meeting.id)).filter(Meeting.status == "cancelled").scalar() or 0,
        "no_show": db.query(func.count(Meeting.id)).filter(Meeting.status == "no_show").scalar() or 0,
        "calendar_live": False,
    }
