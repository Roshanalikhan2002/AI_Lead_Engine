"""Build outreach context and select eligible contacts."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.ai_qualification import AIQualification
from app.models.email_verification import EmailVerification
from app.models.lead import Lead
from app.models.lead_contact import LeadContact
from app.models.website_analysis import WebsiteAnalysis

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
BLOCKED_VERIFICATION = frozenset({"invalid", "blocked", "risky", "error"})


class ContactSelectionError(ValueError):
    pass


def is_syntactically_valid_email(email: str | None) -> bool:
    if not email:
        return False
    return bool(EMAIL_RE.match(email.strip()))


def select_outreach_contact(
    db: Session,
    lead_id: uuid.UUID,
    *,
    contact_id: uuid.UUID | None = None,
    allow_unknown: bool = False,
) -> tuple[LeadContact, EmailVerification | None]:
    contacts = (
        db.query(LeadContact)
        .filter(LeadContact.lead_id == lead_id)
        .order_by(LeadContact.is_primary.desc(), LeadContact.created_at.asc())
        .all()
    )
    if not contacts:
        raise ContactSelectionError("No contacts discovered for lead")

    ver_by_id = {
        v.lead_contact_id: v
        for v in db.query(EmailVerification)
        .filter(EmailVerification.lead_contact_id.in_([c.id for c in contacts]))
        .all()
    }

    candidates = contacts
    if contact_id is not None:
        candidates = [c for c in contacts if c.id == contact_id]
        if not candidates:
            raise ContactSelectionError("Contact does not belong to this lead")

    # Prefer valid verification
    ordered: list[tuple[LeadContact, EmailVerification | None]] = []
    for c in candidates:
        if not is_syntactically_valid_email(c.normalized_email or c.email):
            continue
        v = ver_by_id.get(c.id)
        status = v.status if v else "not_verified"
        if status in BLOCKED_VERIFICATION:
            continue
        if status == "valid":
            ordered.insert(0, (c, v))
        elif status == "unknown" and allow_unknown:
            ordered.append((c, v))
        elif status == "not_verified" and allow_unknown:
            ordered.append((c, v))
        # default: skip unknown / not_verified unless allow_unknown

    if not ordered:
        raise ContactSelectionError(
            "No eligible contact: require verification_status=valid "
            "(or enable OUTREACH_ALLOW_UNKNOWN_VERIFICATION for unknown)"
        )
    return ordered[0]


def build_outreach_context(
    db: Session,
    lead: Lead,
    contact: LeadContact,
    verification: EmailVerification | None,
    *,
    qualification: AIQualification | None = None,
    analysis: WebsiteAnalysis | None = None,
    prompt_version: str = "v1.0",
    agency_name: str = "LeadFlow AI",
) -> dict[str, Any]:
    if qualification is None:
        qualification = (
            db.query(AIQualification).filter(AIQualification.lead_id == lead.id).one_or_none()
        )
    if analysis is None:
        analysis = db.query(WebsiteAnalysis).filter(WebsiteAnalysis.lead_id == lead.id).one_or_none()

    website_block = None
    if analysis is not None:
        website_block = {
            "website_score": analysis.website_score,
            "seo_score": analysis.seo_score,
            "mobile_score": analysis.mobile_score,
            "has_booking": analysis.has_booking,
            "has_chatbot": analysis.has_chatbot,
            "has_clear_cta": analysis.has_clear_cta,
            "has_contact_form": analysis.has_contact_form,
            "technology": list(analysis.technology_detected or []) or None,
            "analysis_status": analysis.analysis_status,
        }

    qual_block = None
    if qualification is not None:
        qual_block = {
            "lead_score": qualification.lead_score,
            "priority": qualification.priority,
            "primary_service": qualification.primary_service,
            "reason": qualification.primary_reason,
            "evidence": list(qualification.primary_evidence or []),
            "status": qualification.status,
        }

    return {
        "business": {
            "name": lead.company_name,
            "industry": lead.industry,
            "city": lead.city,
            "country": lead.country,
            "rating": lead.rating,
            "review_count": lead.review_count,
            "website": lead.website,
        },
        "website": website_block,
        "qualification": qual_block,
        "contact": {
            "email": contact.normalized_email or contact.email,
            "type": contact.contact_type,
            "verification_status": verification.status if verification else "not_verified",
        },
        "meta": {
            "prompt_version": prompt_version,
            "agency_name": agency_name,
        },
    }


def hash_outreach_context(context: dict[str, Any]) -> str:
    canonical = json.dumps(context, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
