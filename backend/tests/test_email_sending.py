"""Phase 7 email sending tests — mock/test mode only, NO real emails."""

from __future__ import annotations

import hashlib
import hmac
import uuid

import pytest

from app.core.config import Settings, get_settings
from app.models.ai_qualification import AIQualification
from app.models.email_message import EmailMessage
from app.models.email_suppression import EmailSuppression
from app.models.email_verification import EmailVerification
from app.models.lead import Lead
from app.models.lead_contact import LeadContact
from app.models.outreach_draft import OutreachDraft
from app.services.sending.providers import (
    HttpEmailProvider,
    MockEmailProvider,
    UnconfiguredEmailProvider,
    get_email_sending_provider,
)
from app.services.sending.service import SendError, send_approved_draft
from app.services.sending.suppression import add_suppression, is_suppressed
from app.services.sending.webhooks import handle_email_webhook, verify_webhook_signature


def _seed_approved_draft(db, *, verification="valid", draft_status="approved", email="info@abc.example"):
    lead = Lead(
        id=uuid.uuid4(),
        company_name="ABC Dental",
        website="https://abc.example",
        source="google_places_mock",
    )
    contact = LeadContact(
        id=uuid.uuid4(),
        lead_id=lead.id,
        email=email,
        normalized_email=email.lower(),
        contact_type="business",
        source="website",
        confidence="high",
        domain_match=True,
        is_primary=True,
    )
    qual = AIQualification(
        id=uuid.uuid4(),
        lead_id=lead.id,
        status="qualified",
        lead_score=90,
        priority="hot",
        primary_service="appointment_automation",
        provider="mock",
    )
    draft = OutreachDraft(
        id=uuid.uuid4(),
        lead_id=lead.id,
        contact_id=contact.id,
        status=draft_status,
        selected_subject="Quick idea for ABC Dental",
        body="Hi ABC Dental team,\n\nI couldn't find an online booking option on the website.\n\nBest,\nLeadFlow AI",
        service="appointment_automation",
        personalization_points=["No booking system detected"],
        provider="mock",
        generation_status="generated",
    )
    db.add_all([lead, contact, qual, draft])
    db.flush()
    if verification is not None:
        db.add(
            EmailVerification(
                id=uuid.uuid4(),
                lead_contact_id=contact.id,
                status=verification,
                provider="mock",
                is_valid=verification == "valid",
            )
        )
    db.commit()
    return lead, contact, draft


def test_unconfigured_and_mock_providers():
    assert UnconfiguredEmailProvider().send_email(
        sender_email="a@b.com",
        sender_name="A",
        recipient_email="c@d.com",
        subject="s",
        body="b",
        idempotency_key="k",
    ).status == "failed"
    mock = MockEmailProvider().send_email(
        sender_email="a@b.com",
        sender_name="A",
        recipient_email="c@d.com",
        subject="s",
        body="b",
        idempotency_key="k",
    )
    assert mock.status == "simulated"
    assert mock.test_mode is True
    assert mock.provider_message_id and mock.provider_message_id.startswith("mock_")


def test_factory_defaults_to_mock_in_test_mode():
    provider = get_email_sending_provider(
        Settings(EMAIL_TEST_MODE=True, EMAIL_SEND_ENABLED=False, EMAIL_SENDING_PROVIDER="http")
    )
    assert provider.name == "mock"


def test_approved_draft_can_send_simulated(db_session, monkeypatch):
    monkeypatch.setenv("EMAIL_TEST_MODE", "true")
    monkeypatch.setenv("EMAIL_SEND_ENABLED", "false")
    get_settings.cache_clear()
    _, _, draft = _seed_approved_draft(db_session)
    msg = send_approved_draft(db_session, draft.id, provider=MockEmailProvider())
    assert msg.status == "simulated"
    assert msg.test_mode is True
    assert msg.provider_message_id
    assert "unsubscribe" in msg.body.lower()
    assert msg.status != "delivered"
    get_settings.cache_clear()


def test_unapproved_draft_cannot_send(db_session):
    _, _, draft = _seed_approved_draft(db_session, draft_status="draft")
    with pytest.raises(SendError) as exc:
        send_approved_draft(db_session, draft.id, provider=MockEmailProvider())
    assert exc.value.code == "draft_not_approved"


def test_invalid_risky_unknown_cannot_send(db_session):
    for status in ("invalid", "risky", "unknown"):
        _, _, draft = _seed_approved_draft(db_session, verification=status, email=f"{status}@abc.example")
        with pytest.raises(SendError) as exc:
            send_approved_draft(db_session, draft.id, provider=MockEmailProvider())
        assert exc.value.code == "verification_required"


def test_suppressed_cannot_send(db_session):
    _, contact, draft = _seed_approved_draft(db_session)
    add_suppression(db_session, contact.normalized_email, reason="unsubscribe", source="test")
    with pytest.raises(SendError) as exc:
        send_approved_draft(db_session, draft.id, provider=MockEmailProvider())
    assert exc.value.code == "recipient_suppressed"


def test_idempotency_prevents_duplicate_send(db_session, monkeypatch):
    monkeypatch.setenv("EMAIL_TEST_MODE", "true")
    get_settings.cache_clear()
    _, _, draft = _seed_approved_draft(db_session)
    first = send_approved_draft(db_session, draft.id, provider=MockEmailProvider())
    second = send_approved_draft(db_session, draft.id, provider=MockEmailProvider())
    assert first.id == second.id
    count = db_session.query(EmailMessage).filter(EmailMessage.outreach_draft_id == draft.id).count()
    assert count == 1
    get_settings.cache_clear()


def test_unsubscribe_idempotent(db_session):
    row1 = add_suppression(db_session, "Owner@ABC.Example", reason="unsubscribe", source="api")
    row2 = add_suppression(db_session, "owner@abc.example", reason="unsubscribe", source="api")
    assert row1.id == row2.id
    assert is_suppressed(db_session, "OWNER@abc.example") is not None


def test_hard_bounce_and_complaint_suppression(db_session, monkeypatch):
    monkeypatch.setenv("EMAIL_TEST_MODE", "true")
    get_settings.cache_clear()
    _, contact, draft = _seed_approved_draft(db_session)
    msg = send_approved_draft(db_session, draft.id, provider=MockEmailProvider())
    settings = Settings(EMAIL_TEST_MODE=True, EMAIL_WEBHOOK_SECRET="")
    handle_email_webhook(
        db_session,
        settings=settings,
        provider="mock",
        payload={"event": "bounced", "message_id": msg.provider_message_id, "email": contact.normalized_email},
        raw_body=b"{}",
        signature_header=None,
    )
    db_session.refresh(msg)
    assert msg.status == "bounced"
    assert is_suppressed(db_session, contact.normalized_email) is not None

    _, contact2, draft2 = _seed_approved_draft(db_session, email="other@abc.example")
    msg2 = send_approved_draft(db_session, draft2.id, provider=MockEmailProvider())
    handle_email_webhook(
        db_session,
        settings=settings,
        provider="mock",
        payload={"event": "complaint", "message_id": msg2.provider_message_id, "email": contact2.normalized_email},
        raw_body=b"{}",
        signature_header=None,
    )
    db_session.refresh(msg2)
    assert msg2.status == "failed"
    assert is_suppressed(db_session, contact2.normalized_email).reason == "complaint"
    get_settings.cache_clear()


def test_webhook_signature_required_when_secret_set():
    settings = Settings(EMAIL_TEST_MODE=False, EMAIL_SEND_ENABLED=True, EMAIL_WEBHOOK_SECRET="secret")
    body = b'{"event":"delivered"}'
    sig = hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    assert verify_webhook_signature(settings=settings, body=body, signature_header=f"sha256={sig}")
    assert not verify_webhook_signature(settings=settings, body=body, signature_header="bad")


def test_webhook_delivery_does_not_invent(db_session, monkeypatch):
    monkeypatch.setenv("EMAIL_TEST_MODE", "true")
    get_settings.cache_clear()
    _, _, draft = _seed_approved_draft(db_session)
    msg = send_approved_draft(db_session, draft.id, provider=MockEmailProvider())
    assert msg.status == "simulated"
    settings = Settings(EMAIL_TEST_MODE=True, EMAIL_WEBHOOK_SECRET="")
    updated = handle_email_webhook(
        db_session,
        settings=settings,
        provider="mock",
        payload={"event": "delivered", "message_id": msg.provider_message_id},
        raw_body=b"{}",
        signature_header=None,
    )
    assert updated is not None
    assert updated.status == "delivered"
    assert updated.delivered_at is not None
    get_settings.cache_clear()


def test_http_provider_timeout():
    class TimeoutClient:
        @staticmethod
        def post(*args, **kwargs):
            raise TimeoutError("timeout")

    result = HttpEmailProvider(
        api_url="https://example.com/send",
        api_key="k",
        max_retries=0,
        client=TimeoutClient(),
    ).send_email(
        sender_email="a@b.com",
        sender_name="A",
        recipient_email="c@d.com",
        subject="s",
        body="b",
        idempotency_key="k1",
    )
    assert result.status == "failed"
    assert result.retryable is True


def test_rate_limit(db_session, monkeypatch):
    monkeypatch.setenv("EMAIL_TEST_MODE", "true")
    monkeypatch.setenv("MAX_EMAILS_PER_HOUR", "1")
    get_settings.cache_clear()
    _, _, draft1 = _seed_approved_draft(db_session, email="one@abc.example")
    send_approved_draft(db_session, draft1.id, provider=MockEmailProvider())
    _, _, draft2 = _seed_approved_draft(db_session, email="two@abc.example")
    with pytest.raises(SendError) as exc:
        send_approved_draft(db_session, draft2.id, provider=MockEmailProvider())
    assert exc.value.code == "rate_limit_exceeded"
    get_settings.cache_clear()


def test_sending_api(client, SessionLocal, monkeypatch):
    monkeypatch.setenv("EMAIL_TEST_MODE", "true")
    monkeypatch.setenv("EMAIL_SEND_ENABLED", "false")
    get_settings.cache_clear()

    db = SessionLocal()
    lead, contact, draft = _seed_approved_draft(db)
    draft_id = draft.id
    lead_id = lead.id
    contact_id = contact.id
    contact_email = contact.normalized_email
    db.close()

    # unapproved blocked
    db = SessionLocal()
    d = db.get(OutreachDraft, draft_id)
    d.status = "draft"
    db.commit()
    db.close()
    bad = client.post(f"/api/outreach/{draft_id}/send")
    assert bad.status_code == 400

    db = SessionLocal()
    d = db.get(OutreachDraft, draft_id)
    d.status = "approved"
    db.commit()
    db.close()

    ok = client.post(f"/api/outreach/{draft_id}/send")
    assert ok.status_code == 200
    body = ok.json()
    assert body["status"] == "simulated"
    assert body["test_mode"] is True
    assert "api_key" not in str(body).lower()

    # idempotent
    again = client.post(f"/api/outreach/{draft_id}/send")
    assert again.status_code == 200
    assert again.json()["message_id"] == body["message_id"]

    msgs = client.get(f"/api/outreach/{draft_id}/messages")
    assert msgs.status_code == 200
    assert len(msgs.json()) == 1

    unsub = client.post("/api/unsubscribe", json={"email": contact_email})
    assert unsub.status_code == 200

    # suppressed blocks new send for another approved draft to same email
    db = SessionLocal()
    new_draft = OutreachDraft(
        id=uuid.uuid4(),
        lead_id=lead_id,
        contact_id=contact_id,
        status="approved",
        selected_subject="Another",
        body="Body text for send attempt.",
        service="appointment_automation",
        provider="mock",
        generation_status="generated",
    )
    db.add(new_draft)
    db.commit()
    new_id = new_draft.id
    db.close()
    blocked = client.post(f"/api/outreach/{new_id}/send")
    assert blocked.status_code == 400

    stats = client.get("/api/sending/stats")
    assert stats.status_code == 200
    assert "delivery_data_available" in stats.json()

    page = client.get("/unsubscribe", params={"email": "extra@abc.example"})
    assert page.status_code == 200
    assert b"unsubscribed" in page.content.lower()

    get_settings.cache_clear()


def test_webhook_api_auth(client, SessionLocal, monkeypatch):
    monkeypatch.setenv("EMAIL_TEST_MODE", "true")
    monkeypatch.setenv("EMAIL_WEBHOOK_SECRET", "whsec")
    get_settings.cache_clear()

    db = SessionLocal()
    _, _, draft = _seed_approved_draft(db, email="wh@abc.example")
    msg = send_approved_draft(db, draft.id, provider=MockEmailProvider())
    provider_id = msg.provider_message_id
    db.close()

    payload = {"event": "delivered", "message_id": provider_id}
    import json

    raw = json.dumps(payload).encode()
    # wrong signature
    bad = client.post("/api/webhooks/email/mock", content=raw, headers={"Content-Type": "application/json", "X-Signature": "sha256=dead"})
    # With EMAIL_TEST_MODE true and secret set, signature is still required when secret present
    assert bad.status_code in {401, 200}  # verify: secret set => must be 401
    # Actually verify_webhook_signature with secret requires valid sig
    assert bad.status_code == 401

    sig = hmac.new(b"whsec", raw, hashlib.sha256).hexdigest()
    good = client.post(
        "/api/webhooks/email/mock",
        content=raw,
        headers={"Content-Type": "application/json", "X-Signature": f"sha256={sig}"},
    )
    assert good.status_code == 200
    assert good.json()["updated"] is True
    get_settings.cache_clear()
