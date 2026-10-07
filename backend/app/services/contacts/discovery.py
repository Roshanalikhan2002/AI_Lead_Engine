"""Public website contact discovery — evidence-based only."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.contact_discovery import ContactDiscovery
from app.models.contact_discovery_job import ContactDiscoveryJob
from app.models.lead import Lead
from app.models.lead_contact import LeadContact
from app.services.contacts.email_extract import (
    classify_contact_type,
    compute_confidence,
    domains_match,
    extract_emails_from_html,
    guess_contact_name,
    pick_primary,
    source_label,
)
from app.services.website.crawler import WebsiteCrawler

logger = logging.getLogger(__name__)

CONTACT_PATHS = [
    "/",
    "/contact",
    "/contact-us",
    "/about",
    "/about-us",
    "/team",
    "/staff",
    "/support",
    "/book",
    "/booking",
]


def run_contact_discovery_job(job_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        job = db.get(ContactDiscoveryJob, job_id)
        if not job:
            logger.error("Contact discovery job not found: %s", job_id)
            return
        job.status = "running"
        db.commit()

        lead_ids = [uuid.UUID(str(x)) for x in (job.lead_ids or [])]
        for lead_id in lead_ids:
            try:
                discover_lead_contacts(db, lead_id)
                job.succeeded += 1
            except Exception:
                logger.exception("Contact discovery failed lead=%s", lead_id)
                job.failed += 1
                _mark_failed(db, lead_id, "Contact discovery failed due to an unexpected server error.")
            job.processed += 1
            db.commit()

        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.info(
            "Contact discovery job completed job=%s succeeded=%s failed=%s",
            job_id,
            job.succeeded,
            job.failed,
        )
    except Exception:
        logger.exception("Contact discovery job crashed job=%s", job_id)
        try:
            job = db.get(ContactDiscoveryJob, job_id)
            if job:
                job.status = "failed"
                job.error_message = "Contact discovery job failed."
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()


def discover_lead_contacts(
    db: Session,
    lead_id: uuid.UUID,
    *,
    crawler: WebsiteCrawler | None = None,
    replace_existing: bool = True,
) -> ContactDiscovery:
    lead = db.get(Lead, lead_id)
    if not lead:
        raise ValueError("Lead not found")

    discovery = db.query(ContactDiscovery).filter(ContactDiscovery.lead_id == lead_id).one_or_none()
    if discovery is None:
        discovery = ContactDiscovery(lead_id=lead_id, status="pending")
        db.add(discovery)
        db.flush()

    discovery.status = "running"
    discovery.error_message = None
    db.commit()

    website = (lead.website or "").strip()
    if not website:
        if replace_existing:
            db.query(LeadContact).filter(LeadContact.lead_id == lead_id).delete()
        discovery.status = "not_available"
        discovery.emails_found = 0
        discovery.error_message = None
        discovery.discovered_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("Contact discovery not_available lead=%s", lead_id)
        return discovery

    owns = crawler is None
    crawler = crawler or WebsiteCrawler(max_pages=8, max_depth=0, respect_robots=True)
    try:
        if owns:
            crawler.__enter__()
        crawl = crawler.fetch_url_list(website, CONTACT_PATHS)
    finally:
        if owns:
            crawler.__exit__(None, None, None)

    if crawl.blocked:
        discovery.status = "failed"
        discovery.error_message = crawl.error_message or "Blocked by robots.txt"
        discovery.discovered_at = datetime.now(timezone.utc)
        db.commit()
        return discovery

    if not crawl.reachable:
        discovery.status = "failed"
        discovery.error_message = crawl.error_message or "Website unreachable"
        discovery.discovered_at = datetime.now(timezone.utc)
        db.commit()
        return discovery

    extracted = []
    for page in crawl.pages:
        extracted.extend(extract_emails_from_html(page.html, page.final_url or page.url))

    # Dedupe by normalized email, keep strongest evidence
    by_email: dict[str, object] = {}
    for item in extracted:
        prev = by_email.get(item.normalized_email)
        if prev is None:
            by_email[item.normalized_email] = item
            continue
        # Prefer mailto + contact page
        score = (_method_score(item.extraction_method), _page_score(item.page_kind))
        prev_score = (_method_score(prev.extraction_method), _page_score(prev.page_kind))  # type: ignore[attr-defined]
        if score > prev_score:
            by_email[item.normalized_email] = item

    contact_payloads = []
    for item in by_email.values():
        domain_ok = domains_match(item.normalized_email, website)  # type: ignore[attr-defined]
        contact_type = classify_contact_type(item.normalized_email)  # type: ignore[attr-defined]
        confidence = compute_confidence(
            method=item.extraction_method,  # type: ignore[attr-defined]
            page_kind=item.page_kind,  # type: ignore[attr-defined]
            domain_match=domain_ok,
        )
        contact_payloads.append(
            {
                "email": item.email,  # type: ignore[attr-defined]
                "normalized_email": item.normalized_email,  # type: ignore[attr-defined]
                "contact_name": guess_contact_name(item.normalized_email),  # type: ignore[attr-defined]
                "contact_type": contact_type,
                "source": source_label(item.page_kind, item.extraction_method),  # type: ignore[attr-defined]
                "source_url": item.source_url,  # type: ignore[attr-defined]
                "confidence": confidence,
                "domain_match": domain_ok,
            }
        )

    primary = pick_primary(contact_payloads)

    if replace_existing:
        db.query(LeadContact).filter(LeadContact.lead_id == lead_id).delete()

    for payload in contact_payloads:
        existing = (
            db.query(LeadContact)
            .filter(
                LeadContact.lead_id == lead_id,
                LeadContact.normalized_email == payload["normalized_email"],
            )
            .one_or_none()
        )
        if existing:
            for key, value in payload.items():
                setattr(existing, key, value)
            existing.is_primary = payload["normalized_email"] == primary
        else:
            db.add(
                LeadContact(
                    lead_id=lead_id,
                    is_primary=payload["normalized_email"] == primary,
                    role=None,
                    **payload,
                )
            )

    discovery.emails_found = len(contact_payloads)
    discovery.status = "completed" if contact_payloads else "no_public_email"
    discovery.error_message = None
    discovery.discovered_at = datetime.now(timezone.utc)
    db.commit()
    logger.info(
        "Contact discovery lead=%s status=%s emails=%s",
        lead_id,
        discovery.status,
        discovery.emails_found,
    )
    return discovery


def _method_score(method: str) -> int:
    return {"mailto": 3, "visible": 2, "obfuscated": 1}.get(method, 0)


def _page_score(page_kind: str) -> int:
    return {"contact": 5, "team": 4, "about": 3, "support": 3, "booking": 3, "home": 2}.get(page_kind, 1)


def _mark_failed(db: Session, lead_id: uuid.UUID, message: str) -> None:
    discovery = db.query(ContactDiscovery).filter(ContactDiscovery.lead_id == lead_id).one_or_none()
    if discovery is None:
        discovery = ContactDiscovery(lead_id=lead_id)
        db.add(discovery)
    discovery.status = "failed"
    discovery.error_message = message
    discovery.discovered_at = datetime.now(timezone.utc)
