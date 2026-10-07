"""Phase 9 — Conversations & reply intelligence API."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage
from app.models.inbound_email import InboundEmail
from app.models.lead import Lead
from app.models.lead_contact import LeadContact
from app.models.reply_classification import ReplyClassification
from app.models.reply_suggestion import ReplySuggestion
from app.schemas.replies import (
    ConversationMessageRead,
    ConversationRead,
    InboundSimulateRequest,
    ReplyAnalyticsResponse,
    ReplyClassificationRead,
    ReplySuggestionRead,
    ReplySuggestionUpdate,
)
from app.schemas.sending import SendEmailResponse
from app.services.replies.analytics import reply_analytics
from app.services.replies.service import (
    classify_inbound,
    generate_suggestion,
    ingest_inbound_email,
    process_inbound,
)
from app.services.replies.send import send_approved_suggestion
from app.services.sending.service import SendError

router = APIRouter(tags=["conversations"])


def _enrich_conversation(db: Session, conv: Conversation) -> ConversationRead:
    payload = ConversationRead.model_validate(conv)
    if conv.lead_id:
        lead = db.get(Lead, conv.lead_id)
        payload.business_name = lead.company_name if lead else None
    if conv.contact_id:
        contact = db.get(LeadContact, conv.contact_id)
        payload.contact_email = (contact.normalized_email or contact.email) if contact else None
    last = (
        db.query(ConversationMessage)
        .filter(ConversationMessage.conversation_id == conv.id)
        .order_by(ConversationMessage.created_at.desc())
        .first()
    )
    if last:
        payload.preview = (last.body or "")[:160]
    return payload


@router.get("/api/conversations", response_model=list[ConversationRead])
def list_conversations(
    db: Session = Depends(get_db),
    status: str | None = None,
    intent: str | None = None,
    sort: str = Query(default="newest", pattern="^(newest|oldest|priority)$"),
) -> list[ConversationRead]:
    q = db.query(Conversation)
    if status and status != "all":
        # Map UI filter aliases
        status_map = {
            "interested": "interested",
            "meeting_requested": "meeting_requested",
            "questions": "needs_human",
            "pricing": "needs_human",
            "not_interested": "not_interested",
            "unsubscribe": "unsubscribe",
            "needs_human": "needs_human",
            "unknown": "needs_human",
            "open": "open",
            "closed": "closed",
        }
        mapped = status_map.get(status, status)
        q = q.filter(Conversation.status == mapped)
    if intent:
        q = q.filter(Conversation.last_intent == intent)
    if sort == "oldest":
        q = q.order_by(Conversation.last_message_at.asc().nullslast())
    elif sort == "priority":
        # meeting / interested first via status order then newest
        q = q.order_by(Conversation.status.asc(), Conversation.last_message_at.desc().nullslast())
    else:
        q = q.order_by(Conversation.last_message_at.desc().nullslast())
    return [_enrich_conversation(db, c) for c in q.limit(200).all()]


@router.get("/api/conversations/{conversation_id}", response_model=ConversationRead)
def get_conversation(conversation_id: uuid.UUID, db: Session = Depends(get_db)) -> ConversationRead:
    conv = db.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return _enrich_conversation(db, conv)


@router.get("/api/conversations/{conversation_id}/messages", response_model=list[ConversationMessageRead])
def list_messages(conversation_id: uuid.UUID, db: Session = Depends(get_db)) -> list[ConversationMessageRead]:
    if not db.get(Conversation, conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    rows = (
        db.query(ConversationMessage)
        .filter(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.created_at.asc())
        .all()
    )
    return [ConversationMessageRead.model_validate(r) for r in rows]


@router.get("/api/conversations/{conversation_id}/classification", response_model=ReplyClassificationRead | None)
def get_classification(conversation_id: uuid.UUID, db: Session = Depends(get_db)):
    if not db.get(Conversation, conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    row = (
        db.query(ReplyClassification)
        .filter(ReplyClassification.conversation_id == conversation_id)
        .order_by(ReplyClassification.created_at.desc())
        .first()
    )
    return ReplyClassificationRead.model_validate(row) if row else None


@router.get("/api/conversations/{conversation_id}/suggestions", response_model=list[ReplySuggestionRead])
def list_suggestions(conversation_id: uuid.UUID, db: Session = Depends(get_db)) -> list[ReplySuggestionRead]:
    if not db.get(Conversation, conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    rows = (
        db.query(ReplySuggestion)
        .filter(ReplySuggestion.conversation_id == conversation_id)
        .order_by(ReplySuggestion.created_at.desc())
        .all()
    )
    return [ReplySuggestionRead.model_validate(r) for r in rows]


@router.post("/api/conversations/{conversation_id}/classify", response_model=ReplyClassificationRead)
def classify_conversation(conversation_id: uuid.UUID, db: Session = Depends(get_db)) -> ReplyClassificationRead:
    if not db.get(Conversation, conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    inbound = (
        db.query(InboundEmail)
        .filter(InboundEmail.conversation_id == conversation_id)
        .order_by(InboundEmail.received_at.desc())
        .first()
    )
    if not inbound:
        raise HTTPException(status_code=400, detail="No inbound email to classify")
    try:
        row = classify_inbound(db, inbound.id, force=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ReplyClassificationRead.model_validate(row)


@router.post("/api/conversations/{conversation_id}/suggestions/generate", response_model=ReplySuggestionRead)
@router.post("/api/conversations/{conversation_id}/reply-suggestions/generate", response_model=ReplySuggestionRead)
def generate_reply_suggestion(conversation_id: uuid.UUID, db: Session = Depends(get_db)) -> ReplySuggestionRead:
    try:
        row = generate_suggestion(db, conversation_id, force=False)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ReplySuggestionRead.model_validate(row)


@router.post("/api/conversations/{conversation_id}/suggestions/regenerate", response_model=ReplySuggestionRead)
@router.post("/api/conversations/{conversation_id}/reply-suggestions/regenerate", response_model=ReplySuggestionRead)
def regenerate_reply_suggestion(conversation_id: uuid.UUID, db: Session = Depends(get_db)) -> ReplySuggestionRead:
    try:
        row = generate_suggestion(db, conversation_id, force=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ReplySuggestionRead.model_validate(row)


@router.patch("/api/reply-suggestions/{suggestion_id}", response_model=ReplySuggestionRead)
def update_suggestion(
    suggestion_id: uuid.UUID, payload: ReplySuggestionUpdate, db: Session = Depends(get_db)
) -> ReplySuggestionRead:
    suggestion = db.get(ReplySuggestion, suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    if suggestion.status == "sent":
        raise HTTPException(status_code=400, detail="Cannot edit a sent suggestion")
    data = payload.model_dump(exclude_unset=True)
    if "subject" in data:
        suggestion.subject = data["subject"]
    if "body" in data and data["body"] is not None:
        suggestion.body = data["body"]
    suggestion.status = "edited"
    suggestion.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(suggestion)
    return ReplySuggestionRead.model_validate(suggestion)


@router.post("/api/reply-suggestions/{suggestion_id}/approve", response_model=ReplySuggestionRead)
def approve_suggestion(suggestion_id: uuid.UUID, db: Session = Depends(get_db)) -> ReplySuggestionRead:
    suggestion = db.get(ReplySuggestion, suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    if suggestion.status not in {"draft", "edited", "rejected"}:
        raise HTTPException(status_code=400, detail=f"Cannot approve from status={suggestion.status}")
    suggestion.status = "approved"
    suggestion.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(suggestion)
    return ReplySuggestionRead.model_validate(suggestion)


@router.post("/api/reply-suggestions/{suggestion_id}/reject", response_model=ReplySuggestionRead)
def reject_suggestion(suggestion_id: uuid.UUID, db: Session = Depends(get_db)) -> ReplySuggestionRead:
    suggestion = db.get(ReplySuggestion, suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    if suggestion.status == "sent":
        raise HTTPException(status_code=400, detail="Cannot reject a sent suggestion")
    suggestion.status = "rejected"
    suggestion.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(suggestion)
    return ReplySuggestionRead.model_validate(suggestion)


@router.post("/api/reply-suggestions/{suggestion_id}/send", response_model=SendEmailResponse)
def send_suggestion(suggestion_id: uuid.UUID, db: Session = Depends(get_db)) -> SendEmailResponse:
    """Explicit send only — AI never auto-sends."""
    try:
        message = send_approved_suggestion(db, suggestion_id)
    except SendError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}) from exc
    return SendEmailResponse(
        status=message.status,
        message_id=message.id,
        provider_message_id=message.provider_message_id,
        test_mode=message.test_mode,
        error_code=message.error_code,
        error_message=message.error_message,
    )


@router.post("/api/replies/inbound/simulate")
def simulate_inbound(payload: InboundSimulateRequest, db: Session = Depends(get_db)) -> dict:
    """Offline/dev intake — uses mock provider path; does not claim live provider receipt."""
    try:
        inbound = ingest_inbound_email(
            db,
            provider="mock",
            payload={
                "from_email": payload.from_email,
                "to_email": payload.to_email,
                "subject": payload.subject,
                "body": payload.body,
                "provider_message_id": payload.provider_message_id or f"sim-{uuid.uuid4()}",
                "thread_id": payload.thread_id,
                "in_reply_to": payload.in_reply_to,
                "event": "inbound",
            },
            auto_process=payload.auto_process,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "inbound_email_id": str(inbound.id),
        "conversation_id": str(inbound.conversation_id) if inbound.conversation_id else None,
        "match_confidence": inbound.match_confidence,
        "match_method": inbound.match_method,
        "provider": "mock",
        "live": False,
    }


@router.get("/api/replies/stats", response_model=ReplyAnalyticsResponse)
def replies_stats(db: Session = Depends(get_db)) -> ReplyAnalyticsResponse:
    return ReplyAnalyticsResponse(**reply_analytics(db))
