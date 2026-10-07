"""Normalize inbound email provider webhooks."""

from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.email_message import EmailMessage
from app.services.sending.service import apply_webhook_event

logger = logging.getLogger(__name__)

INBOUND_EVENT_TYPES = frozenset(
    {
        "inbound",
        "incoming",
        "reply",
        "email.received",
        "email.inbound",
        "inbound_email",
        "message.inbound",
    }
)


def verify_webhook_signature(
    *,
    settings: Settings,
    body: bytes,
    signature_header: str | None,
) -> bool:
    """
    Simple HMAC-SHA256 verification when EMAIL_WEBHOOK_SECRET is set.
    Header format: sha256=<hex> or raw hex.
    If secret is empty, allow only when test mode / send disabled.
    """
    secret = (settings.email_webhook_secret or "").strip()
    if not secret:
        return bool(settings.email_test_mode or not settings.email_send_enabled)
    if not signature_header:
        return False
    provided = signature_header.strip()
    if provided.startswith("sha256="):
        provided = provided[7:]
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, provided)


def normalize_webhook_payload(provider: str, payload: dict[str, Any]) -> dict[str, str | None]:
    event_type = (
        payload.get("event")
        or payload.get("type")
        or payload.get("event_type")
        or payload.get("status")
        or ""
    )
    message_id = (
        payload.get("provider_message_id")
        or payload.get("message_id")
        or payload.get("id")
    )
    data = payload.get("data")
    if not message_id and isinstance(data, dict):
        message_id = data.get("message_id") or data.get("id")
    email = payload.get("email") or payload.get("recipient") or payload.get("to")
    if isinstance(email, list) and email:
        email = email[0]
    if isinstance(email, dict):
        email = email.get("email")
    return {
        "event_type": str(event_type).lower() if event_type else "",
        "provider_message_id": str(message_id) if message_id else None,
        "recipient_email": str(email).lower() if email else None,
        "provider": provider,
    }


def is_inbound_event(payload: dict[str, Any]) -> bool:
    event = str(
        payload.get("event")
        or payload.get("type")
        or payload.get("event_type")
        or payload.get("direction")
        or ""
    ).lower()
    if event in INBOUND_EVENT_TYPES:
        return True
    if payload.get("direction") == "inbound":
        return True
    if payload.get("inbound") is True:
        return True
    return False


def handle_email_webhook(
    db: Session,
    *,
    settings: Settings,
    provider: str,
    payload: dict[str, Any],
    raw_body: bytes,
    signature_header: str | None,
) -> EmailMessage | dict | None:
    if not verify_webhook_signature(settings=settings, body=raw_body, signature_header=signature_header):
        raise PermissionError("Invalid webhook signature")

    if is_inbound_event(payload):
        if not settings.reply_inbound_enabled and not settings.email_test_mode:
            logger.info("Inbound webhook ignored: REPLY_INBOUND_ENABLED=false")
            return None
        from app.services.replies.service import ingest_inbound_email

        inbound = ingest_inbound_email(db, provider=provider, payload=payload, auto_process=True)
        return {"inbound_email_id": str(inbound.id), "conversation_id": str(inbound.conversation_id)}

    normalized = normalize_webhook_payload(provider, payload)
    if not normalized["provider_message_id"]:
        logger.info("Webhook ignored: missing message id provider=%s", provider)
        return None

    return apply_webhook_event(
        db,
        provider=provider,
        provider_message_id=normalized["provider_message_id"],
        event_type=normalized["event_type"] or "",
        recipient_email=normalized["recipient_email"],
    )
