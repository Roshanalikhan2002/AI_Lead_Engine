"""Orchestrates email deliverability verification — separate from discovery confidence."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.email_verification import EmailVerification
from app.models.email_verification_job import EmailVerificationJob
from app.models.lead import Lead
from app.models.lead_contact import LeadContact
from app.services.verification.providers import (
    EmailVerificationProvider,
    ProviderResult,
    get_verification_provider,
)
from app.services.verification.signals import (
    check_mx,
    email_domain,
    is_free_email_provider,
    is_role_based_email,
)

logger = logging.getLogger(__name__)


def run_email_verification_job(job_id: uuid.UUID) -> None:
    db = SessionLocal()
    settings = get_settings()
    try:
        job = db.get(EmailVerificationJob, job_id)
        if not job:
            logger.error("Email verification job not found: %s", job_id)
            return
        job.status = "running"
        db.commit()

        provider = get_verification_provider(settings)
        contact_ids = [uuid.UUID(str(x)) for x in (job.contact_ids or [])]

        for contact_id in contact_ids:
            try:
                result = verify_contact(
                    db,
                    contact_id,
                    provider=provider,
                    force=False,
                )
                _bump_job_counters(job, result.status)
            except Exception:
                logger.exception("Email verification failed contact=%s", contact_id)
                job.failed_count += 1
            job.processed += 1
            db.commit()
            time.sleep(max(0.0, settings.verification_request_delay_seconds))

        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("Email verification job completed job=%s processed=%s", job_id, job.processed)
    except Exception:
        logger.exception("Email verification job crashed job=%s", job_id)
        try:
            job = db.get(EmailVerificationJob, job_id)
            if job:
                job.status = "failed"
                job.error_message = "Email verification job failed."
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()


def verify_lead_contact(
    db: Session,
    lead_id: uuid.UUID,
    contact_id: uuid.UUID,
    *,
    force: bool = False,
    provider: EmailVerificationProvider | None = None,
    mx_checker=None,
) -> EmailVerification:
    contact = db.get(LeadContact, contact_id)
    if not contact or contact.lead_id != lead_id:
        raise ValueError("Contact not found for lead")
    return verify_contact(db, contact_id, force=force, provider=provider, mx_checker=mx_checker)


def verify_contact(
    db: Session,
    contact_id: uuid.UUID,
    *,
    force: bool = False,
    provider: EmailVerificationProvider | None = None,
    mx_checker=None,
) -> EmailVerification:
    settings = get_settings()
    contact = db.get(LeadContact, contact_id)
    if not contact:
        raise ValueError("Contact not found")

    existing = (
        db.query(EmailVerification).filter(EmailVerification.lead_contact_id == contact_id).one_or_none()
    )
    if existing and not force and _is_fresh(existing, settings.verification_cache_days):
        return existing

    provider = provider or get_verification_provider(settings)
    domain = email_domain(contact.normalized_email)
    mx = mx_checker(domain) if mx_checker else check_mx(domain)
    role_based = is_role_based_email(contact.normalized_email)
    free_provider = is_free_email_provider(contact.normalized_email)

    provider_result = provider.verify_email(contact.normalized_email)
    merged = _merge_result(
        provider_result,
        mx_found=mx,
        is_role_based=role_based,
        is_free_provider=free_provider,
    )

    if existing is None:
        existing = EmailVerification(lead_contact_id=contact_id)
        db.add(existing)

    existing.status = merged.status
    existing.provider = merged.provider_name
    existing.provider_summary = merged.summary
    existing.is_valid = merged.is_valid
    existing.is_risky = merged.is_risky
    existing.is_disposable = merged.is_disposable
    existing.is_role_based = True if role_based else merged.is_role_based
    existing.is_free_provider = True if free_provider else merged.is_free_provider
    existing.mx_found = mx if mx is not None else merged.mx_found
    existing.domain = domain
    existing.verified_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(existing)
    logger.info(
        "Email verified contact=%s status=%s provider=%s",
        contact_id,
        existing.status,
        existing.provider,
    )
    return existing


def _merge_result(
    result: ProviderResult,
    *,
    mx_found: bool | None,
    is_role_based: bool,
    is_free_provider: bool,
) -> ProviderResult:
    status = result.status
    is_valid = result.is_valid
    is_risky = result.is_risky
    is_disposable = result.is_disposable

    # Never upgrade to valid based on MX alone
    if status == "valid" and result.provider_name in {"none"}:
        status = "unknown"
        is_valid = None

    if is_disposable is True and status not in {"invalid", "error"}:
        status = "risky"
        is_risky = True

    # Role / free are signals, not validity
    return ProviderResult(
        status=status,
        is_valid=is_valid,
        is_risky=is_risky,
        is_disposable=is_disposable,
        is_role_based=is_role_based if is_role_based else result.is_role_based,
        is_free_provider=is_free_provider if is_free_provider else result.is_free_provider,
        mx_found=mx_found if mx_found is not None else result.mx_found,
        summary=result.summary,
        provider_name=result.provider_name,
    )


def _is_fresh(row: EmailVerification, cache_days: int) -> bool:
    if not row.verified_at or row.status == "pending":
        return False
    verified_at = row.verified_at
    if verified_at.tzinfo is None:
        verified_at = verified_at.replace(tzinfo=timezone.utc)
    return verified_at >= datetime.now(timezone.utc) - timedelta(days=max(0, cache_days))


def _bump_job_counters(job: EmailVerificationJob, status: str) -> None:
    if status == "valid":
        job.valid_count += 1
    elif status == "invalid":
        job.invalid_count += 1
    elif status == "risky":
        job.risky_count += 1
    elif status in {"unknown", "blocked"}:
        job.unknown_count += 1
    else:
        job.failed_count += 1
