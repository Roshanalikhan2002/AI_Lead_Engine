"""Campaign step execution with idempotency and concurrency safety."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.campaign import Campaign
from app.models.campaign_recipient import CampaignRecipient
from app.models.campaign_step import CampaignStep
from app.models.campaign_step_execution import CampaignStepExecution
from app.models.email_message import EmailMessage
from app.models.email_verification import EmailVerification
from app.models.lead_contact import LeadContact
from app.models.outreach_draft import OutreachDraft
from app.services.campaigns.scheduler import compute_next_send_at, is_within_send_window
from app.services.campaigns.states import (
    RECIPIENT_TERMINAL,
    assert_recipient_transition,
    maybe_complete_campaign,
)
from app.services.sending.service import SendError, check_rate_limits, send_approved_draft
from app.services.sending.suppression import is_suppressed, normalize_email

logger = logging.getLogger(__name__)


def execution_key_for(campaign_id: uuid.UUID, recipient_id: uuid.UUID, step_number: int) -> str:
    return f"campaign:{campaign_id}:recipient:{recipient_id}:step:{step_number}"


class CampaignExecutionService:
    """Provider-agnostic campaign step executor (Celery/Redis swap-ready)."""

    def __init__(self, db: Session, *, worker_id: str | None = None):
        self.db = db
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self.settings = get_settings()

    def claim_due_recipients(self, *, limit: int | None = None) -> list[CampaignRecipient]:
        limit = limit or self.settings.campaign_scheduler_batch_size
        now = datetime.now(timezone.utc)
        lock_ttl = timedelta(seconds=self.settings.campaign_lock_ttl_seconds)
        stale_before = now - lock_ttl

        due = (
            self.db.query(CampaignRecipient)
            .join(Campaign, Campaign.id == CampaignRecipient.campaign_id)
            .filter(
                Campaign.status == "active",
                CampaignRecipient.status == "active",
                CampaignRecipient.next_action_at.isnot(None),
                CampaignRecipient.next_action_at <= now,
            )
            .order_by(CampaignRecipient.next_action_at.asc())
            .limit(limit * 3)
            .all()
        )

        claimed: list[CampaignRecipient] = []
        for recipient in due:
            if recipient.locked_at and recipient.locked_at > stale_before:
                continue
            recipient.locked_at = now
            recipient.locked_by = self.worker_id
            claimed.append(recipient)
            if len(claimed) >= limit:
                break
        self.db.commit()
        return claimed

    def check_campaign_rate_limits(self, campaign: Campaign) -> None:
        now = datetime.now(timezone.utc)
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)

        hour_count = (
            self.db.query(func.count(CampaignStepExecution.id))
            .filter(
                CampaignStepExecution.campaign_id == campaign.id,
                CampaignStepExecution.status.in_(["sent", "simulated"]),
                CampaignStepExecution.created_at >= hour_ago,
            )
            .scalar()
            or 0
        )
        day_count = (
            self.db.query(func.count(CampaignStepExecution.id))
            .filter(
                CampaignStepExecution.campaign_id == campaign.id,
                CampaignStepExecution.status.in_(["sent", "simulated"]),
                CampaignStepExecution.created_at >= day_ago,
            )
            .scalar()
            or 0
        )
        if hour_count >= campaign.hourly_send_limit:
            raise SendError("Campaign hourly limit reached", code="campaign_rate_limit", status_code=429)
        if day_count >= campaign.daily_send_limit:
            raise SendError("Campaign daily limit reached", code="campaign_rate_limit", status_code=429)

        # Global limits — never bypass
        check_rate_limits(self.db)

    def _release_lock(self, recipient: CampaignRecipient) -> None:
        recipient.locked_at = None
        recipient.locked_by = None

    def execute_recipient(self, recipient_id: uuid.UUID) -> dict:
        recipient = self.db.get(CampaignRecipient, recipient_id)
        if not recipient:
            return {"ok": False, "reason": "recipient_not_found"}

        campaign = self.db.get(Campaign, recipient.campaign_id)
        if not campaign:
            return {"ok": False, "reason": "campaign_not_found"}

        try:
            return self._execute(campaign, recipient)
        finally:
            self._release_lock(recipient)
            self.db.commit()

    def _execute(self, campaign: Campaign, recipient: CampaignRecipient) -> dict:
        now = datetime.now(timezone.utc)

        if campaign.status != "active":
            return {"ok": False, "reason": "campaign_not_active", "skipped": True}
        if recipient.status != "active":
            return {"ok": False, "reason": "recipient_not_active", "skipped": True}

        if campaign.start_at and now < campaign.start_at:
            recipient.next_action_at = compute_next_send_at(campaign, campaign.start_at)
            return {"ok": False, "reason": "campaign_not_started", "skipped": True}
        if campaign.end_at and now > campaign.end_at:
            assert_recipient_transition(recipient.status, "cancelled")
            recipient.status = "cancelled"
            recipient.completed_at = now
            recipient.next_action_at = None
            maybe_complete_campaign(self.db, campaign)
            return {"ok": False, "reason": "campaign_ended"}

        if not is_within_send_window(campaign, now):
            recipient.next_action_at = compute_next_send_at(campaign, now)
            return {"ok": False, "reason": "outside_send_window", "skipped": True}

        next_step_number = recipient.current_step + 1
        step = (
            self.db.query(CampaignStep)
            .filter(
                CampaignStep.campaign_id == campaign.id,
                CampaignStep.step_number == next_step_number,
            )
            .one_or_none()
        )
        if not step:
            assert_recipient_transition(recipient.status, "completed")
            recipient.status = "completed"
            recipient.completed_at = now
            recipient.next_action_at = None
            maybe_complete_campaign(self.db, campaign)
            return {"ok": True, "reason": "sequence_complete"}

        if step.type != "email":
            recipient.last_error = f"Unsupported step type: {step.type}"
            assert_recipient_transition(recipient.status, "failed")
            recipient.status = "failed"
            recipient.completed_at = now
            recipient.next_action_at = None
            maybe_complete_campaign(self.db, campaign)
            return {"ok": False, "reason": "unsupported_step_type"}

        # Safety checks
        contact = self.db.get(LeadContact, recipient.contact_id)
        if not contact or contact.lead_id != recipient.lead_id:
            recipient.last_error = "Contact ownership invalid"
            assert_recipient_transition(recipient.status, "failed")
            recipient.status = "failed"
            recipient.completed_at = now
            recipient.next_action_at = None
            return {"ok": False, "reason": "contact_ownership"}

        email = normalize_email(contact.normalized_email or contact.email)
        if is_suppressed(self.db, email):
            assert_recipient_transition(recipient.status, "unsubscribed")
            recipient.status = "unsubscribed"
            recipient.completed_at = now
            recipient.next_action_at = None
            maybe_complete_campaign(self.db, campaign)
            return {"ok": False, "reason": "suppressed"}

        verification = (
            self.db.query(EmailVerification)
            .filter(EmailVerification.lead_contact_id == contact.id)
            .one_or_none()
        )
        if not verification or verification.status != "valid":
            recipient.last_error = "Email no longer valid"
            assert_recipient_transition(recipient.status, "failed")
            recipient.status = "failed"
            recipient.completed_at = now
            recipient.next_action_at = None
            maybe_complete_campaign(self.db, campaign)
            return {"ok": False, "reason": "verification_invalid"}

        draft_id = step.outreach_draft_id or recipient.outreach_draft_id
        draft = self.db.get(OutreachDraft, draft_id)
        if (
            not draft
            or draft.status != "approved"
            or draft.lead_id != recipient.lead_id
            or draft.contact_id != recipient.contact_id
        ):
            recipient.last_error = "Approved draft missing"
            assert_recipient_transition(recipient.status, "failed")
            recipient.status = "failed"
            recipient.completed_at = now
            recipient.next_action_at = None
            maybe_complete_campaign(self.db, campaign)
            return {"ok": False, "reason": "approved_draft_required"}

        if not self.settings.email_send_enabled and not self.settings.email_test_mode:
            # Both false is unusual; treat as blocked
            return {"ok": False, "reason": "email_send_disabled", "skipped": True}

        key = execution_key_for(campaign.id, recipient.id, step.step_number)
        existing_exec = (
            self.db.query(CampaignStepExecution)
            .filter(CampaignStepExecution.execution_key == key)
            .one_or_none()
        )
        if existing_exec and existing_exec.status in {"sent", "simulated"}:
            # Idempotent: advance without re-send
            self._advance_after_send(campaign, recipient, step, now)
            return {"ok": True, "reason": "already_executed", "idempotent": True}

        try:
            self.check_campaign_rate_limits(campaign)
        except SendError as exc:
            # Push next_action slightly ahead; do not fail permanently
            recipient.next_action_at = compute_next_send_at(campaign, now + timedelta(minutes=15))
            recipient.last_error = str(exc)[:255]
            return {"ok": False, "reason": exc.code, "skipped": True}

        if not existing_exec:
            existing_exec = CampaignStepExecution(
                campaign_id=campaign.id,
                campaign_recipient_id=recipient.id,
                step_number=step.step_number,
                execution_key=key,
                status="pending",
            )
            self.db.add(existing_exec)
            try:
                self.db.commit()
            except IntegrityError:
                self.db.rollback()
                existing_exec = (
                    self.db.query(CampaignStepExecution)
                    .filter(CampaignStepExecution.execution_key == key)
                    .one()
                )
                if existing_exec.status in {"sent", "simulated"}:
                    self._advance_after_send(campaign, recipient, step, now)
                    return {"ok": True, "reason": "already_executed", "idempotent": True}

        try:
            message = send_approved_draft(
                self.db,
                draft.id,
                idempotency_key=key,
                skip_global_rate_limit=True,  # already checked via check_campaign_rate_limits
            )
        except SendError as exc:
            existing_exec.status = "failed"
            existing_exec.error_message = str(exc)[:255]
            existing_exec.completed_at = now
            recipient.last_error = str(exc)[:255]
            if exc.code in {
                "recipient_suppressed",
                "verification_required",
                "draft_not_approved",
                "contact_mismatch",
            }:
                target = "unsubscribed" if exc.code == "recipient_suppressed" else "failed"
                assert_recipient_transition(recipient.status, target)
                recipient.status = target
                recipient.completed_at = now
                recipient.next_action_at = None
                maybe_complete_campaign(self.db, campaign)
            else:
                # Retryable / rate — defer
                recipient.next_action_at = compute_next_send_at(campaign, now + timedelta(minutes=30))
            self.db.commit()
            return {"ok": False, "reason": exc.code}

        existing_exec.email_message_id = message.id
        existing_exec.completed_at = datetime.now(timezone.utc)
        if message.status in {"sent", "simulated"}:
            existing_exec.status = message.status
            recipient.last_sent_at = existing_exec.completed_at
            recipient.last_error = None
            self._advance_after_send(campaign, recipient, step, existing_exec.completed_at)
            self.db.commit()
            return {
                "ok": True,
                "step": step.step_number,
                "message_id": str(message.id),
                "status": message.status,
            }

        existing_exec.status = "failed"
        existing_exec.error_message = (message.error_message or message.status)[:255]
        recipient.last_error = existing_exec.error_message
        if message.status in {"bounced", "blocked"}:
            assert_recipient_transition(recipient.status, "bounced" if message.status == "bounced" else "failed")
            recipient.status = "bounced" if message.status == "bounced" else "failed"
            recipient.completed_at = now
            recipient.next_action_at = None
            maybe_complete_campaign(self.db, campaign)
        else:
            recipient.next_action_at = compute_next_send_at(campaign, now + timedelta(minutes=30))
        self.db.commit()
        return {"ok": False, "reason": "send_failed", "status": message.status}

    def _advance_after_send(
        self,
        campaign: Campaign,
        recipient: CampaignRecipient,
        step: CampaignStep,
        when: datetime,
    ) -> None:
        recipient.current_step = step.step_number
        next_step = (
            self.db.query(CampaignStep)
            .filter(
                CampaignStep.campaign_id == campaign.id,
                CampaignStep.step_number == step.step_number + 1,
            )
            .one_or_none()
        )
        if not next_step:
            assert_recipient_transition(recipient.status, "completed")
            recipient.status = "completed"
            recipient.completed_at = when
            recipient.next_action_at = None
            maybe_complete_campaign(self.db, campaign)
            return

        delay = timedelta(minutes=int(next_step.delay_minutes or 0))
        recipient.next_action_at = compute_next_send_at(campaign, when + delay)

    def process_due(self, *, limit: int | None = None) -> dict:
        claimed = self.claim_due_recipients(limit=limit)
        results = []
        for recipient in claimed:
            # refresh after commit
            rid = recipient.id
            results.append(self.execute_recipient(rid))
        return {"processed": len(results), "results": results}


class CampaignScheduler:
    """Thin scheduler facade — swap-ready for Celery beat / Redis workers."""

    def __init__(self, db: Session, *, worker_id: str | None = None):
        self.execution = CampaignExecutionService(db, worker_id=worker_id)

    def tick(self, *, limit: int | None = None) -> dict:
        return self.execution.process_due(limit=limit)
