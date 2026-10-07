"""Build structured AI qualification input from DB entities — no raw HTML."""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.email_verification import EmailVerification
from app.models.lead import Lead
from app.models.lead_contact import LeadContact
from app.models.lead_opportunity import LeadOpportunity
from app.models.website_analysis import WebsiteAnalysis


def build_qualification_input(
    db: Session,
    lead: Lead,
    *,
    analysis: WebsiteAnalysis | None = None,
    opportunities: list[LeadOpportunity] | None = None,
    contacts: list[LeadContact] | None = None,
    verifications: dict[uuid.UUID, EmailVerification] | None = None,
) -> dict[str, Any]:
    if analysis is None:
        analysis = db.query(WebsiteAnalysis).filter(WebsiteAnalysis.lead_id == lead.id).one_or_none()
    if opportunities is None:
        opportunities = (
            db.query(LeadOpportunity)
            .filter(LeadOpportunity.lead_id == lead.id, LeadOpportunity.source == "website_analysis")
            .all()
        )
    if contacts is None:
        contacts = db.query(LeadContact).filter(LeadContact.lead_id == lead.id).all()
    if verifications is None:
        verifications = {
            v.lead_contact_id: v
            for v in db.query(EmailVerification)
            .filter(EmailVerification.lead_contact_id.in_([c.id for c in contacts] or [uuid.uuid4()]))
            .all()
        }

    website_block: dict[str, Any] | None
    if analysis is None:
        website_block = None
    else:
        website_block = {
            "reachable": analysis.reachable,
            "https_enabled": analysis.https_enabled,
            "seo_score": analysis.seo_score,
            "mobile_score": analysis.mobile_score,
            "website_score": analysis.website_score,
            "has_contact_form": analysis.has_contact_form,
            "has_booking": analysis.has_booking,
            "has_chatbot": analysis.has_chatbot,
            "has_clear_cta": analysis.has_clear_cta,
            "technology": list(analysis.technology_detected or []) or None,
            "analysis_status": analysis.analysis_status,
        }

    return {
        "business": {
            "name": lead.company_name,
            "industry": lead.industry,
            "country": lead.country,
            "state": lead.state,
            "city": lead.city,
            "rating": lead.rating,
            "review_count": lead.review_count,
            "website": lead.website,
            "business_status": lead.business_status,
        },
        "website": website_block,
        "deterministic_opportunities": [
            {
                "service": op.service,
                "confidence": op.confidence,
                "evidence": list(op.evidence or []),
                "reason": op.reason,
            }
            for op in (opportunities or [])
        ],
        "contacts": [
            {
                "email": c.normalized_email or c.email,
                "type": c.contact_type,
                "discovery_confidence": c.confidence,
                "verification_status": (
                    verifications[c.id].status if c.id in verifications else "not_verified"
                ),
                "is_role_based": (
                    verifications[c.id].is_role_based if c.id in verifications else None
                ),
            }
            for c in (contacts or [])
        ],
    }


def hash_qualification_input(input_data: dict[str, Any]) -> str:
    canonical = json.dumps(input_data, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
