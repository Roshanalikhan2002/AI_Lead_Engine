from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.models.email_message import EmailMessage
from app.models.email_suppression import EmailSuppression
from app.models.outreach_draft import OutreachDraft
from app.schemas.sending import (
    EmailMessageRead,
    SendEmailResponse,
    SendingStatsResponse,
    UnsubscribeRequest,
    UnsubscribeResponse,
    WebhookAckResponse,
)
from app.services.sending.service import SendError, send_approved_draft
from app.services.sending.suppression import add_suppression, normalize_email
from app.services.sending.webhooks import handle_email_webhook

router = APIRouter(tags=["sending"])


@router.post("/api/outreach/{draft_id}/send", response_model=SendEmailResponse)
def send_outreach_draft(draft_id: uuid.UUID, db: Session = Depends(get_db)) -> SendEmailResponse:
    """Explicit send of an approved draft. Never auto-sends. Acceptance ≠ delivered."""
    try:
        message = send_approved_draft(db, draft_id)
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


@router.get("/api/outreach/{draft_id}/messages", response_model=list[EmailMessageRead])
def list_draft_messages(draft_id: uuid.UUID, db: Session = Depends(get_db)) -> list[EmailMessageRead]:
    draft = db.get(OutreachDraft, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    rows = (
        db.query(EmailMessage)
        .filter(EmailMessage.outreach_draft_id == draft_id)
        .order_by(EmailMessage.created_at.desc())
        .all()
    )
    return [EmailMessageRead.model_validate(r) for r in rows]


@router.get("/api/leads/{lead_id}/messages", response_model=list[EmailMessageRead])
def list_lead_messages(lead_id: uuid.UUID, db: Session = Depends(get_db)) -> list[EmailMessageRead]:
    rows = (
        db.query(EmailMessage)
        .filter(EmailMessage.lead_id == lead_id)
        .order_by(EmailMessage.created_at.desc())
        .all()
    )
    return [EmailMessageRead.model_validate(r) for r in rows]


@router.post("/api/unsubscribe", response_model=UnsubscribeResponse)
def unsubscribe(payload: UnsubscribeRequest, db: Session = Depends(get_db)) -> UnsubscribeResponse:
    email = normalize_email(str(payload.email))
    row = add_suppression(db, email, reason="unsubscribe", source="unsubscribe_api")
    try:
        from app.services.campaigns.events import stop_recipients_for_email

        stop_recipients_for_email(db, email, event_type="unsubscribe")
    except Exception:  # noqa: BLE001
        pass
    return UnsubscribeResponse(status="suppressed", email=row.email, reason=row.reason)


@router.get("/unsubscribe", response_class=HTMLResponse)
def unsubscribe_page(email: str = "", db: Session = Depends(get_db)) -> str:
    """Simple unsubscribe landing — safe to call repeatedly."""
    normalized = normalize_email(email) if email else ""
    if normalized:
        add_suppression(db, normalized, reason="unsubscribe", source="unsubscribe_page")
        try:
            from app.services.campaigns.events import stop_recipients_for_email

            stop_recipients_for_email(db, normalized, event_type="unsubscribe")
        except Exception:  # noqa: BLE001
            pass
        msg = f"<p>You have been unsubscribed: <strong>{normalized}</strong></p>"
    else:
        msg = "<p>Provide an email query parameter to unsubscribe.</p>"
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Unsubscribe</title></head>
<body style="font-family:sans-serif;max-width:560px;margin:40px auto;padding:0 16px">
<h1>Unsubscribe</h1>
{msg}
<p>You will not receive further outreach emails from this system for this address.</p>
</body></html>"""


@router.post("/api/webhooks/email/{provider}", response_model=WebhookAckResponse)
async def email_webhook(
    provider: str,
    request: Request,
    db: Session = Depends(get_db),
) -> WebhookAckResponse:
    settings = get_settings()
    raw = await request.body()
    signature = request.headers.get("X-Signature") or request.headers.get("X-Webhook-Signature")
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from None
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Webhook payload must be an object")
    try:
        updated = handle_email_webhook(
            db,
            settings=settings,
            provider=provider,
            payload=payload,
            raw_body=raw,
            signature_header=signature,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return WebhookAckResponse(status="ok", updated=updated is not None)


@router.get("/api/sending/stats", response_model=SendingStatsResponse)
def sending_stats(db: Session = Depends(get_db)) -> SendingStatsResponse:
    sent = (
        db.query(func.count(EmailMessage.id))
        .filter(EmailMessage.status.in_(["sent", "delivered"]), EmailMessage.test_mode.is_(False))
        .scalar()
        or 0
    )
    delivered = (
        db.query(func.count(EmailMessage.id))
        .filter(EmailMessage.status == "delivered", EmailMessage.test_mode.is_(False))
        .scalar()
        or 0
    )
    bounced = (
        db.query(func.count(EmailMessage.id))
        .filter(EmailMessage.status == "bounced")
        .scalar()
        or 0
    )
    failed = (
        db.query(func.count(EmailMessage.id))
        .filter(EmailMessage.status == "failed")
        .scalar()
        or 0
    )
    simulated = (
        db.query(func.count(EmailMessage.id))
        .filter(EmailMessage.status == "simulated")
        .scalar()
        or 0
    )
    suppressed = db.query(func.count(EmailSuppression.id)).scalar() or 0
    delivery_available = delivered > 0
    rate = round(delivered / sent, 3) if sent > 0 and delivery_available else None
    has_real = sent > 0 or delivered > 0 or bounced > 0
    return SendingStatsResponse(
        emails_sent=sent,
        delivered=delivered,
        bounced=bounced,
        failed=failed,
        suppressed=suppressed,
        simulated=simulated,
        delivery_rate=rate,
        delivery_data_available=delivery_available,
        has_real_data=has_real,
    )
