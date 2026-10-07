from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.generation_job import GenerationJob
from app.models.lead import Lead
from app.services.google_places import GooglePlacesError, GooglePlacesService
from app.services.lead_normalizer import passes_filters, to_lead

logger = logging.getLogger(__name__)


def run_generation_job(job_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        job = db.get(GenerationJob, job_id)
        if not job:
            logger.error("Generation job not found: %s", job_id)
            return

        job.status = "running"
        job.error_message = None
        db.commit()
        logger.info(
            "Generation started job=%s city=%s industry=%s quantity=%s",
            job.id,
            job.city,
            job.industry,
            job.requested_quantity,
        )

        settings = get_settings()
        lead_source = "google_places_mock" if settings.google_places_mock else "google_places"
        with GooglePlacesService(settings) as places:
            businesses = places.search_businesses(
                industry=job.industry,
                keywords=job.keywords,
                city=job.city,
                state=job.state,
                country=job.country,
                min_rating=job.min_rating,
                quantity=job.requested_quantity,
            )

        job = db.get(GenerationJob, job_id)
        if not job:
            return
        job.found_quantity = len(businesses)
        db.commit()
        logger.info("Businesses discovered job=%s count=%s", job.id, len(businesses))

        saved = 0
        duplicates = 0
        processed = 0

        for business in businesses:
            job = db.get(GenerationJob, job_id)
            if not job:
                return

            processed += 1
            job.processed_quantity = processed

            if not passes_filters(
                business,
                min_rating=job.min_rating,
                min_reviews=job.min_reviews,
                website_filter=job.website_filter,
            ):
                db.commit()
                continue

            if _is_duplicate(db, job.organization_id, business.google_place_id):
                duplicates += 1
                job.duplicates_skipped = duplicates
                db.commit()
                logger.info("Duplicate skipped place_id=%s", business.google_place_id)
                continue

            lead = to_lead(
                business,
                industry=job.industry,
                organization_id=job.organization_id,
                generation_job_id=job.id,
                source=lead_source,
            )
            db.add(lead)
            try:
                db.commit()
                saved += 1
                job = db.get(GenerationJob, job_id)
                if job:
                    job.saved_quantity = saved
                    db.commit()
                if job and job.organization_id:
                    try:
                        from app.services.billing.usage import increment_usage

                        increment_usage(db, job.organization_id, "leads_discovered", amount=1, check=False)
                    except Exception:  # noqa: BLE001
                        logger.exception("usage increment leads_discovered failed")
                logger.info("Lead saved company=%s place_id=%s", lead.company_name, lead.google_place_id)
            except IntegrityError:
                db.rollback()
                duplicates += 1
                job = db.get(GenerationJob, job_id)
                if job:
                    job.duplicates_skipped = duplicates
                    job.processed_quantity = processed
                    db.commit()
                logger.info("Duplicate skipped on insert place_id=%s", business.google_place_id)

        job = db.get(GenerationJob, job_id)
        if not job:
            return
        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        job.processed_quantity = processed
        job.saved_quantity = saved
        job.duplicates_skipped = duplicates
        db.commit()
        logger.info(
            "Generation completed job=%s found=%s saved=%s duplicates=%s",
            job.id,
            job.found_quantity,
            saved,
            duplicates,
        )
    except GooglePlacesError as exc:
        logger.exception("Generation failed (Places) job=%s", job_id)
        _fail_job(db, job_id, str(exc))
    except Exception:
        logger.exception("Generation failed job=%s", job_id)
        _fail_job(db, job_id, "Lead generation failed due to an unexpected server error.")
    finally:
        db.close()


def _is_duplicate(db: Session, organization_id, google_place_id: str | None) -> bool:
    if not google_place_id:
        return False
    existing = (
        db.query(Lead.id)
        .filter(Lead.organization_id == organization_id, Lead.google_place_id == google_place_id)
        .first()
    )
    return existing is not None


def _fail_job(db: Session, job_id: uuid.UUID, message: str) -> None:
    try:
        job = db.get(GenerationJob, job_id)
        if not job:
            return
        job.status = "failed"
        job.error_message = message
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
    except Exception:
        logger.exception("Unable to mark job failed job=%s", job_id)
        db.rollback()
