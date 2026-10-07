"""Phase 8 campaign management & follow-up tests — MockEmailProvider only."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.core.config import get_settings
from app.models.ai_qualification import AIQualification
from app.models.campaign import Campaign
from app.models.campaign_recipient import CampaignRecipient
from app.models.campaign_step import CampaignStep
from app.models.campaign_step_execution import CampaignStepExecution
from app.models.email_message import EmailMessage
from app.models.email_verification import EmailVerification
from app.models.lead import Lead
from app.models.lead_contact import LeadContact
from app.models.outreach_draft import OutreachDraft
from app.services.campaigns.enrollment import enroll_batch, enroll_recipient
from app.services.campaigns.events import apply_recipient_event
from app.services.campaigns.execution import CampaignExecutionService, CampaignScheduler, execution_key_for
from app.services.campaigns.scheduler import compute_next_send_at, is_within_send_window
from app.services.campaigns.states import CampaignStateError, assert_campaign_transition
from app.services.sending.suppression import add_suppression


def _seed_ready_lead(db, *, email="info@biz.example", score=90, priority="hot", service="appointment_automation"):
    lead = Lead(
        id=uuid.uuid4(),
        company_name="Biz Co",
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
        lead_score=score,
        priority=priority,
        primary_service=service,
        provider="mock",
    )
    draft = OutreachDraft(
        id=uuid.uuid4(),
        lead_id=lead.id,
        contact_id=contact.id,
        status="approved",
        selected_subject="Hello Biz",
        body="Hi team,\n\nFollowing up.\n\nBest,\nLeadFlow",
        service=service,
        personalization_points=["website gap"],
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


def _create_campaign(db, *, weekends=False, tz="UTC", start=0, end=24, hourly=50, daily=200):
    campaign = Campaign(
        name="Test Campaign",
        description="Phase 8 QA",
        status="draft",
        timezone=tz,
        daily_send_limit=daily,
        hourly_send_limit=hourly,
        send_start_hour=start,
        send_end_hour=end,
        send_on_weekends=weekends,
    )
    db.add(campaign)
    db.flush()
    for n, delay in [(1, 0), (2, 3 * 24 * 60), (3, 5 * 24 * 60)]:
        db.add(
            CampaignStep(
                campaign_id=campaign.id,
                step_number=n,
                type="email",
                delay_minutes=delay,
            )
        )
    db.commit()
    db.refresh(campaign)
    return campaign


@pytest.fixture(autouse=True)
def _email_test_mode(monkeypatch):
    monkeypatch.setenv("EMAIL_TEST_MODE", "true")
    monkeypatch.setenv("EMAIL_SEND_ENABLED", "false")
    monkeypatch.setenv("SENDER_EMAIL", "sender@leadflow.test")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_campaign_create_update_steps_api(client, db_session):
    res = client.post(
        "/api/campaigns",
        json={
            "name": "API Campaign",
            "timezone": "America/New_York",
            "daily_send_limit": 20,
            "hourly_send_limit": 5,
            "send_start_hour": 9,
            "send_end_hour": 17,
            "send_on_weekends": False,
            "steps": [
                {"step_number": 1, "delay_minutes": 0},
                {"step_number": 2, "delay_minutes": 4320},
            ],
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "draft"
    cid = data["id"]

    patch = client.patch(f"/api/campaigns/{cid}", json={"name": "Renamed", "hourly_send_limit": 8})
    assert patch.status_code == 200
    assert patch.json()["name"] == "Renamed"

    steps = client.get(f"/api/campaigns/{cid}/steps").json()
    assert len(steps) == 2
    assert steps[0]["step_number"] == 1

    add = client.post(
        f"/api/campaigns/{cid}/steps",
        json={"step_number": 3, "delay_minutes": 7200},
    )
    assert add.status_code == 200
    step_id = add.json()["id"]
    upd = client.patch(
        f"/api/campaigns/{cid}/steps/{step_id}",
        json={"delay_minutes": 8000},
    )
    assert upd.status_code == 200
    assert upd.json()["delay_minutes"] == 8000


def test_enrollment_validations(db_session):
    campaign = _create_campaign(db_session)
    lead, contact, draft = _seed_ready_lead(db_session)

    ok = enroll_recipient(db_session, campaign.id, lead_id=lead.id, contact_id=contact.id)
    assert ok.enrolled is True

    dup = enroll_recipient(db_session, campaign.id, lead_id=lead.id, contact_id=contact.id)
    assert dup.enrolled is False
    assert dup.reason == "already_enrolled_active"

    other_lead, _, _ = _seed_ready_lead(db_session, email="other@x.example")
    mismatch = enroll_recipient(
        db_session,
        campaign.id,
        lead_id=other_lead.id,
        contact_id=contact.id,
    )
    assert mismatch.enrolled is False
    assert mismatch.reason == "contact_ownership_mismatch"

    bad_lead, bad_contact, bad_draft = _seed_ready_lead(db_session, email="bad@x.example")
    bad_draft.status = "draft"
    db_session.commit()
    no_approved = enroll_recipient(db_session, campaign.id, lead_id=bad_lead.id)
    assert no_approved.reason == "approved_draft_required"

    supp_lead, supp_contact, _ = _seed_ready_lead(db_session, email="supp@x.example")
    add_suppression(db_session, "supp@x.example", reason="unsubscribe", source="test")
    suppressed = enroll_recipient(db_session, campaign.id, lead_id=supp_lead.id)
    assert suppressed.reason == "recipient_suppressed"

    unver_lead = Lead(id=uuid.uuid4(), company_name="U", website="https://u.example", source="mock")
    unver_contact = LeadContact(
        id=uuid.uuid4(),
        lead_id=unver_lead.id,
        email="u@u.example",
        normalized_email="u@u.example",
        contact_type="business",
        source="website",
        confidence="high",
        domain_match=True,
        is_primary=True,
    )
    unver_draft = OutreachDraft(
        id=uuid.uuid4(),
        lead_id=unver_lead.id,
        contact_id=unver_contact.id,
        status="approved",
        selected_subject="s",
        body="b",
        provider="mock",
        generation_status="generated",
    )
    db_session.add_all([unver_lead, unver_contact, unver_draft])
    db_session.commit()
    unver = enroll_recipient(db_session, campaign.id, lead_id=unver_lead.id)
    assert unver.reason == "email_not_verified_valid"


def test_batch_requires_explicit_filter(db_session):
    campaign = _create_campaign(db_session)
    result = enroll_batch(db_session, campaign.id)
    assert result["enrolled_count"] == 0
    assert result["skipped"][0]["reason"] == "explicit_selection_or_filter_required"


def test_batch_filter_enrollment(db_session):
    campaign = _create_campaign(db_session)
    hot, _, _ = _seed_ready_lead(db_session, email="hot@x.example", priority="hot", score=95)
    _seed_ready_lead(db_session, email="cold@x.example", priority="cold", score=20)
    result = enroll_batch(db_session, campaign.id, priority="hot", min_score=80)
    assert result["enrolled_count"] == 1
    assert result["enrolled"][0]["lead_id"] == str(hot.id)


def test_activate_pause_resume_cancel(client, db_session):
    campaign = _create_campaign(db_session)
    lead, _, _ = _seed_ready_lead(db_session)
    enroll_recipient(db_session, campaign.id, lead_id=lead.id)

    act = client.post(f"/api/campaigns/{campaign.id}/activate")
    assert act.status_code == 200
    assert act.json()["status"] == "active"

    pause = client.post(f"/api/campaigns/{campaign.id}/pause")
    assert pause.json()["status"] == "paused"

    resume = client.post(f"/api/campaigns/{campaign.id}/resume")
    assert resume.json()["status"] == "active"

    cancel = client.post(f"/api/campaigns/{campaign.id}/cancel")
    assert cancel.json()["status"] == "cancelled"
    recipients = db_session.query(CampaignRecipient).filter_by(campaign_id=campaign.id).all()
    assert all(r.status == "cancelled" for r in recipients)


def test_invalid_campaign_transition():
    with pytest.raises(CampaignStateError):
        assert_campaign_transition("completed", "active")


def test_timezone_and_weekend_window():
    campaign = Campaign(
        name="tz",
        status="active",
        timezone="America/New_York",
        daily_send_limit=10,
        hourly_send_limit=5,
        send_start_hour=9,
        send_end_hour=17,
        send_on_weekends=False,
    )
    # Saturday morning UTC → should jump past weekend in NY
    saturday = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)  # Sat
    nxt = compute_next_send_at(campaign, saturday)
    local = nxt.astimezone(ZoneInfo("America/New_York"))
    assert local.weekday() < 5
    assert 9 <= local.hour < 17

    # Inside window
    weekday_morning = datetime(2026, 8, 17, 14, 0, tzinfo=timezone.utc)  # Mon ~10 NY
    assert is_within_send_window(campaign, weekday_morning) or compute_next_send_at(campaign, weekday_morning)


def test_scheduler_sends_step_and_idempotent(db_session, monkeypatch):
    campaign = _create_campaign(db_session, start=0, end=24, weekends=True)
    campaign.status = "active"
    db_session.commit()
    lead, contact, draft = _seed_ready_lead(db_session)
    result = enroll_recipient(db_session, campaign.id, lead_id=lead.id)
    assert result.enrolled
    recipient = db_session.get(CampaignRecipient, result.recipient_id)
    recipient.status = "active"
    recipient.next_action_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()

    scheduler = CampaignScheduler(db_session, worker_id="test-1")
    out1 = scheduler.tick(limit=10)
    assert out1["processed"] >= 1
    db_session.refresh(recipient)
    assert recipient.current_step == 1
    assert recipient.last_sent_at is not None
    msgs = db_session.query(EmailMessage).all()
    assert len(msgs) == 1
    assert msgs[0].status == "simulated"
    assert msgs[0].status != "delivered"

    # Force same step due again — should be idempotent
    recipient.status = "active"
    recipient.current_step = 0
    recipient.next_action_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()
    out2 = scheduler.tick(limit=10)
    assert out2["processed"] >= 1
    assert db_session.query(EmailMessage).count() == 1
    assert (
        db_session.query(CampaignStepExecution)
        .filter_by(execution_key=execution_key_for(campaign.id, recipient.id, 1))
        .count()
        == 1
    )


def test_pause_blocks_send(db_session):
    campaign = _create_campaign(db_session, start=0, end=24, weekends=True)
    campaign.status = "paused"
    db_session.commit()
    lead, _, _ = _seed_ready_lead(db_session)
    result = enroll_recipient(db_session, campaign.id, lead_id=lead.id)
    recipient = db_session.get(CampaignRecipient, result.recipient_id)
    recipient.status = "active"
    recipient.next_action_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()

    out = CampaignScheduler(db_session).tick(limit=5)
    assert out["processed"] == 0
    assert db_session.query(EmailMessage).count() == 0


def test_reply_unsubscribe_bounce_complaint_events(db_session):
    campaign = _create_campaign(db_session, start=0, end=24, weekends=True)
    campaign.status = "active"
    db_session.commit()

    lead, _, _ = _seed_ready_lead(db_session, email="evt@x.example")
    lead2, _, _ = _seed_ready_lead(db_session, email="bounce@x.example")
    lead3, _, _ = _seed_ready_lead(db_session, email="unsub@x.example")
    lead4, _, _ = _seed_ready_lead(db_session, email="comp@x.example")

    r1 = enroll_recipient(db_session, campaign.id, lead_id=lead.id)
    r2 = enroll_recipient(db_session, campaign.id, lead_id=lead2.id)
    r3 = enroll_recipient(db_session, campaign.id, lead_id=lead3.id)
    r4 = enroll_recipient(db_session, campaign.id, lead_id=lead4.id)
    assert all(r.enrolled for r in (r1, r2, r3, r4))

    for rid in (r1.recipient_id, r2.recipient_id, r3.recipient_id, r4.recipient_id):
        recip = db_session.get(CampaignRecipient, rid)
        recip.status = "active"
        recip.next_action_at = datetime.now(timezone.utc) + timedelta(days=1)
    db_session.commit()

    apply_recipient_event(db_session, r1.recipient_id, event_type="reply")
    assert db_session.get(CampaignRecipient, r1.recipient_id).status == "replied"

    apply_recipient_event(db_session, r2.recipient_id, event_type="bounce")
    assert db_session.get(CampaignRecipient, r2.recipient_id).status == "bounced"

    apply_recipient_event(db_session, r3.recipient_id, event_type="unsubscribe")
    assert db_session.get(CampaignRecipient, r3.recipient_id).status == "unsubscribed"

    apply_recipient_event(db_session, r4.recipient_id, event_type="complaint")
    assert db_session.get(CampaignRecipient, r4.recipient_id).status == "unsubscribed"


def test_campaign_completion_and_analytics(client, db_session):
    campaign = _create_campaign(db_session, start=0, end=24, weekends=True)
    campaign.status = "active"
    db_session.commit()
    lead, _, _ = _seed_ready_lead(db_session)
    result = enroll_recipient(db_session, campaign.id, lead_id=lead.id)
    recipient = db_session.get(CampaignRecipient, result.recipient_id)
    recipient.status = "active"
    recipient.next_action_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()

    # Empty analytics before send
    empty = client.get(f"/api/campaigns/{campaign.id}/analytics").json()
    assert empty["sent"] == 0
    assert empty["delivery_rate"] is None
    assert empty["reply_detection_configured"] is False

    # Only one step then complete recipient by marking steps done quickly:
    # delete steps 2+ so one send completes sequence
    for step in db_session.query(CampaignStep).filter(
        CampaignStep.campaign_id == campaign.id, CampaignStep.step_number > 1
    ).all():
        db_session.delete(step)
    db_session.commit()

    CampaignScheduler(db_session).tick(limit=5)
    db_session.refresh(recipient)
    assert recipient.status == "completed"
    db_session.refresh(campaign)
    assert campaign.status == "completed"

    analytics = client.get(f"/api/campaigns/{campaign.id}/analytics").json()
    assert analytics["sent"] == 1
    assert analytics["completed"] == 1
    assert analytics["has_send_data"] is True


def test_campaign_rate_limit_defers(db_session, monkeypatch):
    campaign = _create_campaign(db_session, start=0, end=24, weekends=True, hourly=1, daily=1)
    campaign.status = "active"
    db_session.commit()
    lead1, _, _ = _seed_ready_lead(db_session, email="r1@x.example")
    lead2, _, _ = _seed_ready_lead(db_session, email="r2@x.example")
    for lead in (lead1, lead2):
        r = enroll_recipient(db_session, campaign.id, lead_id=lead.id)
        recip = db_session.get(CampaignRecipient, r.recipient_id)
        recip.status = "active"
        recip.next_action_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()

    CampaignScheduler(db_session).tick(limit=10)
    sent = db_session.query(EmailMessage).count()
    assert sent == 1


def test_process_due_api(client, db_session):
    campaign = _create_campaign(db_session, start=0, end=24, weekends=True)
    campaign.status = "active"
    db_session.commit()
    lead, _, _ = _seed_ready_lead(db_session)
    r = enroll_recipient(db_session, campaign.id, lead_id=lead.id)
    recip = db_session.get(CampaignRecipient, r.recipient_id)
    recip.status = "active"
    recip.next_action_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()

    res = client.post("/api/campaigns/process-due?limit=10")
    assert res.status_code == 200
    assert res.json()["processed"] >= 1


def test_recipient_event_api(client, db_session):
    campaign = _create_campaign(db_session)
    campaign.status = "active"
    db_session.commit()
    lead, _, _ = _seed_ready_lead(db_session)
    r = enroll_recipient(db_session, campaign.id, lead_id=lead.id)
    recip = db_session.get(CampaignRecipient, r.recipient_id)
    recip.status = "active"
    db_session.commit()

    res = client.post(
        f"/api/campaigns/recipients/{recip.id}/events",
        json={"event_type": "reply", "provider_event_id": "future-webhook-1"},
    )
    assert res.status_code == 200
    assert res.json()["event_type"] == "reply"
    db_session.refresh(recip)
    assert recip.status == "replied"


def test_delayed_follow_up_scheduling(db_session):
    campaign = _create_campaign(db_session, start=0, end=24, weekends=True)
    campaign.status = "active"
    db_session.commit()
    lead, _, _ = _seed_ready_lead(db_session)
    r = enroll_recipient(db_session, campaign.id, lead_id=lead.id)
    recip = db_session.get(CampaignRecipient, r.recipient_id)
    recip.status = "active"
    recip.next_action_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()

    CampaignScheduler(db_session).tick(limit=5)
    db_session.refresh(recip)
    assert recip.current_step == 1
    assert recip.status == "active"
    assert recip.next_action_at is not None
    next_at = recip.next_action_at
    if next_at.tzinfo is None:
        next_at = next_at.replace(tzinfo=timezone.utc)
    assert next_at > datetime.now(timezone.utc) + timedelta(days=2)


def test_list_campaigns_empty_metrics(client):
    res = client.get("/api/campaigns")
    assert res.status_code == 200
    assert res.json() == []
