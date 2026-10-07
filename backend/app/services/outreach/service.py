"""Orchestrates outreach draft generation — never sends email."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.ai_qualification import AIQualification
from app.models.lead import Lead
from app.models.outreach_draft import OutreachDraft
from app.models.outreach_generation_job import OutreachGenerationJob
from app.services.outreach.context import (
    ContactSelectionError,
    build_outreach_context,
    hash_outreach_context,
    select_outreach_contact,
)
from app.services.outreach.normalize import (
    OutreachGenerationResult,
    insufficient_result,
)
from app.services.outreach.providers import OutreachGenerationProvider, get_outreach_provider

logger = logging.getLogger(__name__)

# Phase 6 must never set status to "sent"
ALLOWED_DRAFT_STATUSES = frozenset({"draft", "approved", "rejected", "edited", "cancelled"})


def run_outreach_generation_job(job_id: uuid.UUID) -> None:
    db = SessionLocal()
    settings = get_settings()
    try:
        job = db.get(OutreachGenerationJob, job_id)
        if not job:
            logger.error("Outreach generation job not found: %s", job_id)
            return
        job.status = "running"
        db.commit()

        provider = get_outreach_provider(settings)
        lead_ids = [uuid.UUID(str(x)) for x in (job.lead_ids or [])]

        for lead_id in lead_ids:
            try:
                row = generate_outreach_draft(db, lead_id, provider=provider, force=False)
                if row.generation_status == "generated" and row.status in {"draft", "edited"}:
                    job.generated_count += 1
                elif row.generation_status in {"insufficient_data", "unconfigured"}:
                    job.skipped_count += 1
                elif row.generation_status == "error":
                    job.failed_count += 1
                else:
                    job.skipped_count += 1
            except ContactSelectionError:
                job.skipped_count += 1
            except Exception:
                logger.exception("Outreach generation failed lead=%s", lead_id)
                job.failed_count += 1
            job.processed += 1
            db.commit()
            time.sleep(max(0.0, settings.outreach_request_delay_seconds))

        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("Outreach job completed job=%s processed=%s", job_id, job.processed)
    except Exception:
        logger.exception("Outreach job crashed job=%s", job_id)
        try:
            job = db.get(OutreachGenerationJob, job_id)
            if job:
                job.status = "failed"
                job.error_message = "Outreach generation job failed."
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()


def generate_outreach_draft(
    db: Session,
    lead_id: uuid.UUID,
    *,
    contact_id: uuid.UUID | None = None,
    force: bool = False,
    provider: OutreachGenerationProvider | None = None,
) -> OutreachDraft:
    settings = get_settings()
    lead = db.get(Lead, lead_id)
    if not lead:
        raise ValueError("Lead not found")

    qualification = db.query(AIQualification).filter(AIQualification.lead_id == lead_id).one_or_none()
    if not qualification or qualification.status not in {"qualified", "not_qualified"}:
        # Still allow generation attempt to store insufficient if no qual — but primary must exist
        pass

    contact, verification = select_outreach_contact(
        db,
        lead_id,
        contact_id=contact_id,
        allow_unknown=settings.outreach_allow_unknown_verification,
    )

    context = build_outreach_context(
        db,
        lead,
        contact,
        verification,
        qualification=qualification,
        prompt_version=settings.outreach_prompt_version,
        agency_name=settings.agency_name,
    )
    input_hash = hash_outreach_context(context)

    existing = (
        db.query(OutreachDraft)
        .filter(OutreachDraft.lead_id == lead_id)
        .order_by(OutreachDraft.updated_at.desc())
        .first()
    )
    if (
        existing
        and not force
        and existing.input_hash == input_hash
        and existing.generation_status == "generated"
        and existing.status in {"draft", "edited", "approved"}
        and existing.body
    ):
        return existing

    primary_service = (qualification.primary_service if qualification else None) or "unknown"
    if primary_service == "unknown" or not qualification:
        result = insufficient_result(
            "Primary service unknown or qualification missing",
            provider_name=(provider.name if provider else "none"),
            prompt_version=settings.outreach_prompt_version,
        )
        return _persist_draft(
            db,
            lead_id=lead_id,
            contact_id=contact.id,
            result=result,
            input_hash=input_hash,
            existing=existing,
            draft_status="draft",
        )

    provider = provider or get_outreach_provider(settings)
    org_id = lead.organization_id
    if org_id:
        from app.services.billing.features import require_feature
        from app.services.billing.usage import check_limit, increment_usage

        require_feature(db, org_id, "ai_outreach")
        check_limit(db, org_id, "ai_generations", amount=1)
    result = provider.generate_email(context)
    draft = _persist_draft(
        db,
        lead_id=lead_id,
        contact_id=contact.id,
        result=result,
        input_hash=input_hash,
        existing=existing,
        draft_status="draft",
    )
    if org_id and result.status == "generated":
        try:
            increment_usage(db, org_id, "ai_generations", amount=1, check=True)
        except Exception:  # noqa: BLE001
            pass
    return draft


def update_outreach_draft(
    db: Session,
    draft_id: uuid.UUID,
    *,
    subject: str | None = None,
    body: str | None = None,
) -> OutreachDraft:
    draft = db.get(OutreachDraft, draft_id)
    if not draft:
        raise ValueError("Draft not found")
    if draft.status == "sent":
        raise ValueError("Cannot edit a sent draft")
    if subject is not None:
        draft.selected_subject = subject.strip()[:255]
    if body is not None:
        draft.body = body.strip()
    if draft.status in {"draft", "approved", "rejected"}:
        draft.status = "edited"
    db.commit()
    db.refresh(draft)
    return draft


def set_draft_status(db: Session, draft_id: uuid.UUID, status: str) -> OutreachDraft:
    if status == "sent":
        raise ValueError("Sending is not available in this phase")
    if status not in ALLOWED_DRAFT_STATUSES:
        raise ValueError("Invalid draft status")
    draft = db.get(OutreachDraft, draft_id)
    if not draft:
        raise ValueError("Draft not found")
    draft.status = status
    db.commit()
    db.refresh(draft)
    return draft


def _persist_draft(
    db: Session,
    *,
    lead_id: uuid.UUID,
    contact_id: uuid.UUID,
    result: OutreachGenerationResult,
    input_hash: str,
    existing: OutreachDraft | None,
    draft_status: str,
) -> OutreachDraft:
    row = existing or OutreachDraft(lead_id=lead_id, contact_id=contact_id)
    if existing is None:
        db.add(row)
    else:
        row.contact_id = contact_id

    # Never set sent
    status = draft_status if draft_status != "sent" else "draft"
    row.status = status if result.status == "generated" else "draft"
    row.selected_subject = result.subjects[0] if result.subjects else None
    row.alternative_subjects = result.subjects[1:] if len(result.subjects) > 1 else []
    row.body = result.body
    row.service = result.service
    row.personalization_points = list(result.personalization_points or [])
    row.provider = result.provider
    row.model = result.model
    row.model_version = result.model_version
    row.prompt_version = result.prompt_version
    row.input_hash = input_hash
    row.generation_status = result.status
    row.error_message = result.error_message
    db.commit()
    db.refresh(row)
    logger.info(
        "Outreach draft saved lead=%s status=%s generation=%s provider=%s",
        lead_id,
        row.status,
        row.generation_status,
        row.provider,
    )
    return row
