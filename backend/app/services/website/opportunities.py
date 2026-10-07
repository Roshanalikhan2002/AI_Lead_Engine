"""Deterministic potential service opportunities — evidence-based only."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.website.crawler import CrawlResult
from app.services.website.html_signals import PageSignals
from app.services.website.scoring import ScoreResult

APPOINTMENT_INDUSTRIES = {
    "dental",
    "dentist",
    "clinic",
    "medical",
    "doctor",
    "salon",
    "spa",
    "barber",
    "lawyer",
    "attorney",
    "real estate",
    "realtor",
    "hotel",
    "restaurant",
    "fitness",
    "gym",
    "therapy",
    "chiropractic",
}


@dataclass
class OpportunityCandidate:
    service: str
    confidence: str  # high | medium | low
    reason: str
    evidence: list[str] = field(default_factory=list)


def detect_opportunities(
    *,
    has_website: bool,
    industry: str | None,
    crawl: CrawlResult | None,
    signals: PageSignals | None,
    scores: ScoreResult | None,
) -> list[OpportunityCandidate]:
    ops: list[OpportunityCandidate] = []

    if not has_website:
        ops.append(
            OpportunityCandidate(
                service="website_development",
                confidence="high",
                reason="Potential opportunity: no website was provided for this business.",
                evidence=["Lead.website is empty"],
            )
        )
        return ops

    if crawl and not crawl.reachable:
        ops.append(
            OpportunityCandidate(
                service="website_development",
                confidence="medium",
                reason="Potential opportunity: website URL exists but could not be reached.",
                evidence=[crawl.error_message or "unreachable"],
            )
        )
        return ops

    if not signals or not scores:
        return ops

    redesign_evidence: list[str] = []
    if scores.seo_score is not None and scores.seo_score < 60:
        redesign_evidence.append(f"SEO basics score {scores.seo_score}/100")
    if scores.mobile_score is not None and scores.mobile_score < 60:
        redesign_evidence.append(f"Mobile readiness score {scores.mobile_score}/100")
    if not signals.has_clear_cta:
        redesign_evidence.append("No clear CTA detected")
    if not signals.has_meta_description:
        redesign_evidence.append("Missing meta description")
    if redesign_evidence:
        ops.append(
            OpportunityCandidate(
                service="website_redesign",
                confidence="high" if len(redesign_evidence) >= 3 else "medium",
                reason="Potential opportunity: website technical/SEO/mobile signals suggest redesign.",
                evidence=redesign_evidence,
            )
        )

    if not signals.has_booking and _industry_likely_appointments(industry):
        ops.append(
            OpportunityCandidate(
                service="appointment_automation",
                confidence="medium",
                reason="Potential opportunity: appointment-oriented industry without detected online booking.",
                evidence=["No booking links/providers detected", f"Industry: {industry or 'unknown'}"],
            )
        )

    if not signals.has_chatbot and _industry_likely_support(industry):
        ops.append(
            OpportunityCandidate(
                service="ai_chatbot",
                confidence="low",
                reason="Potential opportunity: customer-facing business without detected chat widget.",
                evidence=["No known chatbot provider signatures found"],
            )
        )

    if not signals.has_clear_cta or not signals.has_contact_form:
        evidence = []
        if not signals.has_clear_cta:
            evidence.append("No clear CTA")
        if not signals.has_contact_form:
            evidence.append("No contact form")
        ops.append(
            OpportunityCandidate(
                service="lead_capture",
                confidence="medium",
                reason="Potential opportunity: weak lead-capture signals on the website.",
                evidence=evidence,
            )
        )

    if "Shopify" in signals.technology_detected or "WooCommerce" in signals.technology_detected:
        # Not an opportunity by itself — skip ecommerce_development unless broken store signals
        pass
    elif any(k in (industry or "").lower() for k in ("retail", "store", "shop", "ecommerce", "e-commerce")):
        if "Shopify" not in signals.technology_detected and "WooCommerce" not in signals.technology_detected:
            ops.append(
                OpportunityCandidate(
                    service="ecommerce_development",
                    confidence="low",
                    reason="Potential opportunity: retail-oriented industry without detected ecommerce platform.",
                    evidence=[f"Industry: {industry}"],
                )
            )

    return ops


def _industry_likely_appointments(industry: str | None) -> bool:
    text = (industry or "").lower()
    return any(k in text for k in APPOINTMENT_INDUSTRIES)


def _industry_likely_support(industry: str | None) -> bool:
    text = (industry or "").lower()
    return any(
        k in text
        for k in ("dental", "clinic", "hotel", "restaurant", "real estate", "agency", "salon", "medical")
    )
