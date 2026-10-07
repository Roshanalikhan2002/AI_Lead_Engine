"""Orchestrates website crawl → signals → scores → opportunities persistence."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.lead import Lead
from app.models.lead_opportunity import LeadOpportunity
from app.models.website_analysis import WebsiteAnalysis
from app.models.website_analysis_job import WebsiteAnalysisJob
from app.services.website.crawler import WebsiteCrawler
from app.services.website.html_signals import PageSignals, analyze_pages
from app.services.website.opportunities import detect_opportunities
from app.services.website.scoring import ScoreResult, compute_scores
from app.services.website.url_safety import normalize_website_url

logger = logging.getLogger(__name__)

WEBSITE_OPP_SOURCE = "website_analysis"


def run_website_analysis_job(job_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        job = db.get(WebsiteAnalysisJob, job_id)
        if not job:
            logger.error("Website analysis job not found: %s", job_id)
            return
        job.status = "running"
        db.commit()

        lead_ids = [uuid.UUID(str(x)) for x in (job.lead_ids or [])]
        for lead_id in lead_ids:
            try:
                analyze_lead_website(db, lead_id)
                job.succeeded += 1
            except Exception:
                logger.exception("Website analysis failed lead=%s", lead_id)
                job.failed += 1
                _mark_failed(db, lead_id, "Website analysis failed due to an unexpected server error.")
            job.processed += 1
            db.commit()

        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.info(
            "Website analysis job completed job=%s succeeded=%s failed=%s",
            job_id,
            job.succeeded,
            job.failed,
        )
    except Exception:
        logger.exception("Website analysis job crashed job=%s", job_id)
        try:
            job = db.get(WebsiteAnalysisJob, job_id)
            if job:
                job.status = "failed"
                job.error_message = "Website analysis job failed."
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()


def analyze_lead_website(db: Session, lead_id: uuid.UUID, *, crawler: WebsiteCrawler | None = None) -> WebsiteAnalysis:
    lead = db.get(Lead, lead_id)
    if not lead:
        raise ValueError("Lead not found")

    analysis = db.query(WebsiteAnalysis).filter(WebsiteAnalysis.lead_id == lead_id).one_or_none()
    if analysis is None:
        analysis = WebsiteAnalysis(lead_id=lead_id, analysis_status="pending")
        db.add(analysis)
        db.flush()

    analysis.analysis_status = "running"
    analysis.error_message = None
    db.commit()

    raw_website = (lead.website or "").strip()
    if not raw_website:
        _apply_no_website(analysis)
        _replace_opportunities(
            db,
            lead_id,
            detect_opportunities(has_website=False, industry=lead.industry, crawl=None, signals=None, scores=None),
        )
        analysis.analyzed_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("Website analysis not_available lead=%s", lead_id)
        return analysis

    owns = crawler is None
    crawler = crawler or WebsiteCrawler()
    try:
        if owns:
            crawler.__enter__()
        crawl = crawler.crawl(raw_website)
    finally:
        if owns:
            crawler.__exit__(None, None, None)

    analysis.website_url = normalize_website_url(raw_website) or raw_website

    if crawl.blocked:
        analysis.analysis_status = "blocked"
        analysis.reachable = False
        analysis.error_message = crawl.error_message
        analysis.analyzed_at = datetime.now(timezone.utc)
        db.commit()
        return analysis

    if not crawl.reachable:
        analysis.analysis_status = "failed"
        analysis.reachable = False
        analysis.http_status = crawl.http_status
        analysis.final_url = crawl.final_url
        analysis.error_message = crawl.error_message or "Website could not be analyzed"
        analysis.analyzed_at = datetime.now(timezone.utc)
        _replace_opportunities(
            db,
            lead_id,
            detect_opportunities(
                has_website=True,
                industry=lead.industry,
                crawl=crawl,
                signals=None,
                scores=None,
            ),
        )
        db.commit()
        return analysis

    signals = analyze_pages(crawl)
    scores = compute_scores(crawl, signals)
    _apply_crawl_success(analysis, crawl, signals, scores)
    _replace_opportunities(
        db,
        lead_id,
        detect_opportunities(
            has_website=True,
            industry=lead.industry,
            crawl=crawl,
            signals=signals,
            scores=scores,
        ),
    )
    analysis.analysis_status = "completed"
    analysis.analyzed_at = datetime.now(timezone.utc)
    db.commit()
    if lead.organization_id:
        try:
            from app.services.billing.usage import increment_usage

            increment_usage(db, lead.organization_id, "website_analyses", amount=1, check=False)
        except Exception:  # noqa: BLE001
            logger.exception("usage increment website_analyses failed")
    logger.info("Website analysis completed lead=%s score=%s", lead_id, analysis.website_score)
    return analysis


def _apply_no_website(analysis: WebsiteAnalysis) -> None:
    analysis.website_url = None
    analysis.final_url = None
    analysis.http_status = None
    analysis.https_enabled = None
    analysis.reachable = False
    analysis.performance_score = None
    analysis.mobile_score = None
    analysis.seo_score = None
    analysis.accessibility_score = None
    analysis.website_score = None
    analysis.has_title = None
    analysis.has_meta_description = None
    analysis.has_h1 = None
    analysis.has_favicon = None
    analysis.has_canonical = None
    analysis.has_viewport = None
    analysis.has_contact_form = None
    analysis.has_booking = None
    analysis.booking_evidence = None
    analysis.has_chatbot = None
    analysis.chatbot_provider = None
    analysis.has_live_chat = None
    analysis.has_phone = None
    analysis.has_email = None
    analysis.has_address = None
    analysis.has_clear_cta = None
    analysis.cta_evidence = None
    analysis.page_count = 0
    analysis.load_time_ms = None
    analysis.page_size_bytes = None
    analysis.technology_detected = []
    analysis.seo_checks = None
    analysis.score_reasons = ["No website on lead record"]
    analysis.mobile_ready = None
    analysis.analysis_status = "not_available"
    analysis.error_message = None


def _apply_crawl_success(
    analysis: WebsiteAnalysis,
    crawl,
    signals: PageSignals,
    scores: ScoreResult,
) -> None:
    home = crawl.pages[0]
    analysis.final_url = crawl.final_url
    analysis.http_status = crawl.http_status
    analysis.https_enabled = crawl.https_enabled
    analysis.reachable = True
    analysis.performance_score = scores.performance_score
    analysis.mobile_score = scores.mobile_score
    analysis.seo_score = scores.seo_score
    analysis.accessibility_score = scores.accessibility_score
    analysis.website_score = scores.website_score
    analysis.has_title = signals.has_title
    analysis.has_meta_description = signals.has_meta_description
    analysis.has_h1 = signals.has_h1
    analysis.has_favicon = signals.has_favicon
    analysis.has_canonical = signals.has_canonical
    analysis.has_viewport = signals.has_viewport
    analysis.has_contact_form = signals.has_contact_form
    analysis.has_booking = signals.has_booking
    analysis.booking_evidence = signals.booking_evidence
    analysis.has_chatbot = signals.has_chatbot
    analysis.chatbot_provider = signals.chatbot_provider
    analysis.has_live_chat = signals.has_live_chat
    analysis.has_phone = signals.has_phone
    analysis.has_email = signals.has_email
    analysis.has_address = signals.has_address
    analysis.has_clear_cta = signals.has_clear_cta
    analysis.cta_evidence = signals.cta_evidence
    analysis.page_count = len(crawl.pages)
    analysis.load_time_ms = crawl.load_time_ms
    analysis.page_size_bytes = home.page_size_bytes
    analysis.technology_detected = signals.technology_detected
    analysis.seo_checks = scores.seo_checks
    analysis.score_reasons = scores.score_reasons
    analysis.mobile_ready = scores.mobile_ready
    analysis.error_message = None


def _replace_opportunities(db: Session, lead_id: uuid.UUID, candidates) -> None:
    db.query(LeadOpportunity).filter(
        LeadOpportunity.lead_id == lead_id,
        LeadOpportunity.source == WEBSITE_OPP_SOURCE,
    ).delete()
    for cand in candidates:
        db.add(
            LeadOpportunity(
                lead_id=lead_id,
                service=cand.service,
                confidence=cand.confidence,
                reason=cand.reason,
                evidence=cand.evidence,
                source=WEBSITE_OPP_SOURCE,
            )
        )


def _mark_failed(db: Session, lead_id: uuid.UUID, message: str) -> None:
    analysis = db.query(WebsiteAnalysis).filter(WebsiteAnalysis.lead_id == lead_id).one_or_none()
    if analysis is None:
        analysis = WebsiteAnalysis(lead_id=lead_id)
        db.add(analysis)
    analysis.analysis_status = "failed"
    analysis.error_message = message
    analysis.analyzed_at = datetime.now(timezone.utc)
