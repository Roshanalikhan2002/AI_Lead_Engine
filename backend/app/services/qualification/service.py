"""Orchestrates AI lead qualification — evidence-only, cached by input hash."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.ai_qualification import AIQualification
from app.models.ai_qualification_job import AIQualificationJob
from app.models.lead import Lead
from app.services.qualification.input_builder import build_qualification_input, hash_qualification_input
from app.services.qualification.normalize import QualificationResult
from app.services.qualification.providers import AIQualificationProvider, get_qualification_provider

logger = logging.getLogger(__name__)


def run_ai_qualification_job(job_id: uuid.UUID) -> None:
    db = SessionLocal()
    settings = get_settings()
    try:
        job = db.get(AIQualificationJob, job_id)
        if not job:
            logger.error("AI qualification job not found: %s", job_id)
            return
        job.status = "running"
        db.commit()

        provider = get_qualification_provider(settings)
        lead_ids = [uuid.UUID(str(x)) for x in (job.lead_ids or [])]

        for lead_id in lead_ids:
            try:
                row = qualify_lead(db, lead_id, provider=provider, force=False)
                _bump_job_counters(job, row.status)
            except Exception:
                logger.exception("AI qualification failed lead=%s", lead_id)
                job.failed_count += 1
            job.processed += 1
            db.commit()
            time.sleep(max(0.0, settings.ai_request_delay_seconds))

        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("AI qualification job completed job=%s processed=%s", job_id, job.processed)
    except Exception:
        logger.exception("AI qualification job crashed job=%s", job_id)
        try:
            job = db.get(AIQualificationJob, job_id)
            if job:
                job.status = "failed"
                job.error_message = "AI qualification job failed."
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()


def qualify_lead(
    db: Session,
    lead_id: uuid.UUID,
    *,
    force: bool = False,
    provider: AIQualificationProvider | None = None,
) -> AIQualification:
    settings = get_settings()
    lead = db.get(Lead, lead_id)
    if not lead:
        raise ValueError("Lead not found")

    from app.services.billing.features import FeatureNotAvailable, require_feature
    from app.services.billing.usage import UsageLimitError, check_limit, increment_usage

    org_id = lead.organization_id
    if org_id:
        try:
            require_feature(db, org_id, "ai_qualification")
        except FeatureNotAvailable:
            raise

    input_data = build_qualification_input(db, lead)
    input_hash = hash_qualification_input(input_data)

    existing = db.query(AIQualification).filter(AIQualification.lead_id == lead_id).one_or_none()
    if (
        existing
        and not force
        and existing.input_hash == input_hash
        and existing.status in {"qualified", "not_qualified", "insufficient_data", "unconfigured"}
    ):
        return existing

    if org_id:
        check_limit(db, org_id, "ai_qualifications", amount=1)

    provider = provider or get_qualification_provider(settings)
    result = provider.qualify_lead(input_data)
    row = _persist_result(db, lead_id, result, input_hash=input_hash, existing=existing)
    if org_id and result.status not in {"unconfigured", "error", "failed"}:
        try:
            increment_usage(db, org_id, "ai_qualifications", amount=1, check=True)
        except UsageLimitError:
            # Race: work done but counter rejected — still return result; counter stays at limit
            pass
    return row


def _persist_result(
    db: Session,
    lead_id: uuid.UUID,
    result: QualificationResult,
    *,
    input_hash: str,
    existing: AIQualification | None,
) -> AIQualification:
    row = existing or AIQualification(lead_id=lead_id)
    if existing is None:
        db.add(row)

    row.status = result.status
    row.lead_score = result.lead_score
    row.priority = result.priority
    row.business_fit_score = result.business_fit_score
    row.website_opportunity_score = result.website_opportunity_score
    row.automation_opportunity_score = result.automation_opportunity_score
    row.contactability_score = result.contactability_score
    row.evidence_quality_score = result.evidence_quality_score
    row.primary_service = result.primary_service
    row.primary_opportunity_confidence = result.primary_opportunity_confidence
    row.primary_reason = result.primary_reason
    row.primary_evidence = list(result.primary_evidence or [])
    row.additional_opportunities = list(result.additional_opportunities or [])
    row.recommended_action = result.recommended_action
    row.personalization_insights = list(result.personalization_insights or [])
    row.qualification_summary = result.qualification_summary
    row.provider = result.provider
    row.model = result.model
    row.model_version = result.model_version
    row.prompt_version = result.prompt_version
    row.input_hash = input_hash
    row.error_message = result.error_message
    db.commit()
    db.refresh(row)
    logger.info(
        "Lead qualified lead=%s status=%s score=%s provider=%s",
        lead_id,
        row.status,
        row.lead_score,
        row.provider,
    )
    return row


def _bump_job_counters(job: AIQualificationJob, status: str) -> None:
    if status == "qualified":
        job.qualified_count += 1
    elif status == "insufficient_data":
        job.insufficient_data_count += 1
    elif status in {"error", "unconfigured"}:
        job.failed_count += 1
    # not_qualified: counted via processed only
