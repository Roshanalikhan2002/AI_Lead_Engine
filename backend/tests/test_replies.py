"""Phase 9 reply intelligence tests — mock providers only, no real emails."""

from __future__ import annotations

import hashlib
import hmac
import uuid

import pytest

from app.core.config import get_settings
from app.models.ai_qualification import AIQualification
from app.models.campaign import Campaign
from app.models.campaign_recipient import CampaignRecipient
from app.models.campaign_step import CampaignStep
from app.models.conversation import Conversation
from app.models.email_message import EmailMessage
from app.models.email_suppression import EmailSuppression
from app.models.email_verification import EmailVerification
from app.models.inbound_email import InboundEmail
from app.models.lead import Lead
from app.models.lead_contact import LeadContact
from app.models.outreach_draft import OutreachDraft
from app.models.reply_classification import ReplyClassification
from app.models.reply_suggestion import ReplySuggestion
from app.services.replies.providers import (
    MockReplyClassificationProvider,
    MockReplySuggestionProvider,
    get_reply_classification_provider,
)
from app.services.replies.service import ingest_inbound_email, process_inbound
from app.services.replies.send import send_approved_suggestion
from app.services.sending.service import SendError
from app.services.sending.suppression import is_suppressed


def _seed_contact(db, *, email="info@biz.example", company="Biz Co"):
    lead = Lead(
        id=uuid.uuid4(),
        company_name=company,
        website="https://biz.example",
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
        lead_score=88,
        priority="hot",
        primary_service="appointment_automation",
        provider="mock",
    )
    draft = OutreachDraft(
        id=uuid.uuid4(),
        lead_id=lead.id,
        contact_id=contact.id,
        status="approved",
        selected_subject="Quick idea",
        body="Hello",
        service="appointment_automation",
        provider="mock",
        generation_status="generated",
    )
    db.add_all([lead, contact, qual, draft])
    db.flush()
    db.add(
        EmailVerification(
            id=uuid.uuid4(),
            lead_contact_id=contact.id,
            status="valid",
            provider="mock",
            is_valid=True,
        )
    )
    db.commit()
    return lead, contact, draft


def _seed_active_campaign_recipient(db, lead, contact, draft):
    campaign = Campaign(
        name="C",
        status="active",
        timezone="UTC",
        daily_send_limit=50,
        hourly_send_limit=10,
        send_start_hour=0,
        send_end_hour=24,
        send_on_weekends=True,
    )
    db.add(campaign)
    db.flush()
    db.add(CampaignStep(campaign_id=campaign.id, step_number=1, type="email", delay_minutes=0))
    db.add(CampaignStep(campaign_id=campaign.id, step_number=2, type="email", delay_minutes=4320))
    recipient = CampaignRecipient(
        campaign_id=campaign.id,
        lead_id=lead.id,
        contact_id=contact.id,
        outreach_draft_id=draft.id,
        status="active",
        current_step=1,
    )
    db.add(recipient)
    db.commit()
    return campaign, recipient


@pytest.fixture(autouse=True)
def _reply_test_env(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setenv("EMAIL_TEST_MODE", "true")
    monkeypatch.setenv("EMAIL_SEND_ENABLED", "false")
    monkeypatch.setenv("SENDER_EMAIL", "sender@leadflow.test")
    monkeypatch.setenv("REPLY_AUTO_CLASSIFY", "true")
    monkeypatch.setenv("REPLY_AUTO_SUGGEST", "true")
    monkeypatch.setenv("REPLY_INBOUND_ENABLED", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_mock_classifier_intents():
    provider = MockReplyClassificationProvider()
    unsub = provider.classify({"inbound_reply": {"body": "Please remove me from your mailing list."}})
    assert unsub.intent == "unsubscribe"
    meet = provider.classify(
        {"inbound_reply": {"body": "Yes, I'd be interested. Are you free Wednesday afternoon?"}}
    )
    assert meet.intent == "meeting_request"
    price = provider.classify({"inbound_reply": {"body": "Sounds interesting. What does it cost?"}})
    assert price.intent == "pricing_question"
    bad = provider.classify({"inbound_reply": {"body": "malformed-case"}})
    assert bad.intent == "unknown"


def test_anti_hallucination_pricing_suggestion():
    provider = MockReplySuggestionProvider()
    result = provider.suggest(
        {
            "business": {"name": "Biz"},
            "inbound_reply": {"subject": "Re", "body": "Sounds interesting. What does it cost?"},
            "classification": {"intent": "pricing_question"},
        }
    )
    assert "$" not in result.body
    assert "500" not in result.body
    assert "pricing" in result.body.lower()


def test_inbound_match_and_campaign_stop(db_session):
    lead, contact, draft = _seed_contact(db_session)
    _, recipient = _seed_active_campaign_recipient(db_session, lead, contact, draft)

    inbound = ingest_inbound_email(
        db_session,
        provider="mock",
        payload={
            "event": "inbound",
            "from_email": contact.normalized_email,
            "subject": "Re: Quick idea",
            "body": "Yes, I'd be interested. Are you free Wednesday afternoon?",
            "provider_message_id": "inb-1",
        },
    )
    assert inbound.match_confidence == "high"
    assert inbound.lead_id == lead.id
    db_session.refresh(recipient)
    assert recipient.status == "replied"
    assert recipient.next_action_at is None

    conv = db_session.get(Conversation, inbound.conversation_id)
    assert conv is not None
    assert conv.status == "meeting_requested"
    cls = (
        db_session.query(ReplyClassification)
        .filter(ReplyClassification.inbound_email_id == inbound.id)
        .one()
    )
    assert cls.intent == "meeting_request"


def test_unsubscribe_suppression(db_session):
    lead, contact, draft = _seed_contact(db_session, email="bye@biz.example")
    _, recipient = _seed_active_campaign_recipient(db_session, lead, contact, draft)
    inbound = ingest_inbound_email(
        db_session,
        provider="mock",
        payload={
            "event": "inbound",
            "from_email": "bye@biz.example",
            "body": "Please remove me from your mailing list.",
            "provider_message_id": "inb-unsub",
        },
    )
    assert inbound.classification_status == "classified"
    assert is_suppressed(db_session, "bye@biz.example")
    db_session.refresh(recipient)
    assert recipient.status in {"replied", "unsubscribed"}
    conv = db_session.get(Conversation, inbound.conversation_id)
    assert conv.status == "unsubscribe"


def test_unknown_sender_needs_human(db_session):
    inbound = ingest_inbound_email(
        db_session,
        provider="mock",
        payload={
            "event": "inbound",
            "from_email": "stranger@nowhere.example",
            "body": "Hello?",
            "provider_message_id": "inb-unknown",
        },
    )
    assert inbound.match_confidence == "none"
    conv = db_session.get(Conversation, inbound.conversation_id)
    assert conv.status == "needs_human"
    assert conv.lead_id is None


def test_ambiguous_contacts_not_guessed(db_session):
    _seed_contact(db_session, email="shared@x.example", company="A")
    # second lead same email
    lead2 = Lead(id=uuid.uuid4(), company_name="B", website="https://b.example", source="mock")
    contact2 = LeadContact(
        id=uuid.uuid4(),
        lead_id=lead2.id,
        email="shared@x.example",
        normalized_email="shared@x.example",
        contact_type="business",
        source="website",
        confidence="high",
        domain_match=True,
        is_primary=True,
    )
    db_session.add_all([lead2, contact2])
    db_session.commit()

    inbound = ingest_inbound_email(
        db_session,
        provider="mock",
        payload={
            "event": "inbound",
            "from_email": "shared@x.example",
            "body": "hi",
            "provider_message_id": "amb-1",
        },
        auto_process=False,
    )
    assert inbound.match_confidence == "none"
    assert inbound.match_method == "ambiguous_contact_email"
    assert inbound.lead_id is None


def test_duplicate_inbound_idempotent(db_session):
    lead, contact, _ = _seed_contact(db_session)
    a = ingest_inbound_email(
        db_session,
        provider="mock",
        payload={
            "event": "inbound",
            "from_email": contact.normalized_email,
            "body": "Sounds interesting.",
            "provider_message_id": "dup-1",
        },
    )
    b = ingest_inbound_email(
        db_session,
        provider="mock",
        payload={
            "event": "inbound",
            "from_email": contact.normalized_email,
            "body": "Sounds interesting.",
            "provider_message_id": "dup-1",
        },
    )
    assert a.id == b.id
    assert db_session.query(InboundEmail).count() == 1


def test_suggestion_approve_send_not_auto(db_session, monkeypatch):
    lead, contact, _ = _seed_contact(db_session)
    inbound = ingest_inbound_email(
        db_session,
        provider="mock",
        payload={
            "event": "inbound",
            "from_email": contact.normalized_email,
            "subject": "Re",
            "body": "Sounds interesting. Tell me more.",
            "provider_message_id": "sug-1",
        },
    )
    suggestion = (
        db_session.query(ReplySuggestion)
        .filter(ReplySuggestion.conversation_id == inbound.conversation_id)
        .one()
    )
    assert suggestion.status == "draft"
    # Must not send while draft
    with pytest.raises(SendError) as exc:
        send_approved_suggestion(db_session, suggestion.id)
    assert exc.value.code == "not_approved"

    suggestion.status = "approved"
    db_session.commit()
    msg = send_approved_suggestion(db_session, suggestion.id)
    assert msg.status == "simulated"
    assert msg.test_mode is True
    db_session.refresh(suggestion)
    assert suggestion.status == "sent"


def test_webhook_inbound_signature(client, db_session, monkeypatch):
    monkeypatch.setenv("EMAIL_WEBHOOK_SECRET", "whsec")
    monkeypatch.setenv("EMAIL_TEST_MODE", "true")
    get_settings.cache_clear()
    lead, contact, _ = _seed_contact(db_session)

    body = (
        b'{"event":"inbound","from_email":"'
        + contact.normalized_email.encode()
        + b'","body":"Not interested.","provider_message_id":"wh-1"}'
    )
    bad = client.post(
        "/api/webhooks/email/mock",
        content=body,
        headers={"Content-Type": "application/json", "X-Signature": "sha256=deadbeef"},
    )
    assert bad.status_code == 401

    sig = hmac.new(b"whsec", body, hashlib.sha256).hexdigest()
    ok = client.post(
        "/api/webhooks/email/mock",
        content=body,
        headers={"Content-Type": "application/json", "X-Signature": f"sha256={sig}"},
    )
    assert ok.status_code == 200
    assert ok.json()["updated"] is True
    get_settings.cache_clear()


def test_conversations_api_flow(client, db_session):
    lead, contact, _ = _seed_contact(db_session)
    sim = client.post(
        "/api/replies/inbound/simulate",
        json={
            "from_email": contact.normalized_email,
            "subject": "Re",
            "body": "Sounds interesting. What does it cost?",
            "provider_message_id": "api-1",
        },
    )
    assert sim.status_code == 200
    cid = sim.json()["conversation_id"]

    listing = client.get("/api/conversations")
    assert listing.status_code == 200
    assert any(c["id"] == cid for c in listing.json())

    cls = client.get(f"/api/conversations/{cid}/classification").json()
    assert cls["intent"] == "pricing_question"

    sug = client.get(f"/api/conversations/{cid}/suggestions").json()
    assert len(sug) >= 1
    assert "$" not in sug[0]["body"]

    sid = sug[0]["id"]
    edited = client.patch(f"/api/reply-suggestions/{sid}", json={"body": "Thanks — happy to discuss pricing based on your needs."})
    assert edited.json()["status"] == "edited"
    approved = client.post(f"/api/reply-suggestions/{sid}/approve")
    assert approved.json()["status"] == "approved"
    sent = client.post(f"/api/reply-suggestions/{sid}/send")
    assert sent.status_code == 200
    assert sent.json()["status"] == "simulated"

    stats = client.get("/api/replies/stats").json()
    assert stats["has_real_data"] is True
    assert stats["total_replies"] >= 1
    assert stats["reply_tracking_live"] is False


def test_classification_caching(db_session):
    lead, contact, _ = _seed_contact(db_session)
    inbound = ingest_inbound_email(
        db_session,
        provider="mock",
        payload={
            "event": "inbound",
            "from_email": contact.normalized_email,
            "body": "Sounds interesting.",
            "provider_message_id": "cache-1",
        },
    )
    first = db_session.query(ReplyClassification).filter_by(inbound_email_id=inbound.id).count()
    process_inbound(db_session, inbound.id, auto_suggest=False)
    second = db_session.query(ReplyClassification).filter_by(inbound_email_id=inbound.id).count()
    assert first == 1
    assert second == 1


def test_provider_factory_unconfigured(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "")
    get_settings.cache_clear()
    provider = get_reply_classification_provider(get_settings())
    assert provider.name == "none"
    get_settings.cache_clear()


def test_not_interested_stops_campaign(db_session):
    lead, contact, draft = _seed_contact(db_session, email="nope@biz.example")
    _, recipient = _seed_active_campaign_recipient(db_session, lead, contact, draft)
    inbound = ingest_inbound_email(
        db_session,
        provider="mock",
        payload={
            "event": "inbound",
            "from_email": "nope@biz.example",
            "body": "Not interested.",
            "provider_message_id": "ni-1",
        },
    )
    conv = db_session.get(Conversation, inbound.conversation_id)
    assert conv.status == "not_interested"
    db_session.refresh(recipient)
    assert recipient.status == "replied"
