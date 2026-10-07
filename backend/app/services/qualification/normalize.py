"""Normalize / validate AI qualification provider payloads."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.qualification.constants import (
    ALLOWED_CONFIDENCE,
    ALLOWED_SERVICES,
    ALLOWED_STATUSES,
    SCORE_CAPS,
)


@dataclass
class QualificationResult:
    status: str
    lead_score: int | None = None
    priority: str = "unknown"
    business_fit_score: int | None = None
    website_opportunity_score: int | None = None
    automation_opportunity_score: int | None = None
    contactability_score: int | None = None
    evidence_quality_score: int | None = None
    primary_service: str | None = None
    primary_opportunity_confidence: str | None = None
    primary_reason: str | None = None
    primary_evidence: list[str] = field(default_factory=list)
    additional_opportunities: list[dict[str, Any]] = field(default_factory=list)
    recommended_action: str | None = None
    personalization_insights: list[str] = field(default_factory=list)
    qualification_summary: str | None = None
    provider: str = "none"
    model: str | None = None
    model_version: str | None = None
    prompt_version: str | None = None
    error_message: str | None = None


def priority_from_score(score: int | None, status: str) -> str:
    if status in {"insufficient_data", "unconfigured", "error"} or score is None:
        return "unknown"
    if score >= 90:
        return "hot"
    if score >= 70:
        return "warm"
    return "cold"


def _clamp(value: Any, lo: int, hi: int) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = 0
    return max(lo, min(hi, n))


def normalize_provider_payload(
    raw: dict[str, Any],
    *,
    provider_name: str,
    model: str | None = None,
    model_version: str | None = None,
    prompt_version: str | None = None,
) -> QualificationResult:
    """Treat provider JSON as untrusted until validated."""
    if not isinstance(raw, dict):
        return QualificationResult(
            status="error",
            provider=provider_name,
            model=model,
            model_version=model_version,
            prompt_version=prompt_version,
            error_message="Malformed provider response",
        )

    status = str(raw.get("status") or "error").strip().lower()
    if status not in ALLOWED_STATUSES - {"unconfigured"}:
        status = "error"

    factors = raw.get("score_factors") or {}
    if not isinstance(factors, dict):
        factors = {}

    bf = _clamp(factors.get("business_fit", 0), 0, SCORE_CAPS["business_fit"])
    wo = _clamp(factors.get("website_opportunity", 0), 0, SCORE_CAPS["website_opportunity"])
    ao = _clamp(factors.get("automation_opportunity", 0), 0, SCORE_CAPS["automation_opportunity"])
    ct = _clamp(factors.get("contactability", 0), 0, SCORE_CAPS["contactability"])
    eq = _clamp(factors.get("evidence_quality", 0), 0, SCORE_CAPS["evidence_quality"])
    lead_score = bf + wo + ao + ct + eq
    lead_score = max(0, min(100, lead_score))

    primary_service = str(raw.get("primary_service") or "unknown").strip().lower()
    if primary_service not in ALLOWED_SERVICES:
        primary_service = "unknown"

    confidence = str(raw.get("primary_opportunity_confidence") or "unknown").strip().lower()
    if confidence not in ALLOWED_CONFIDENCE:
        confidence = "unknown"

    evidence_raw = raw.get("primary_evidence") or []
    if not isinstance(evidence_raw, list):
        evidence_raw = []
    primary_evidence = [str(x).strip() for x in evidence_raw if str(x).strip()]

    # Evidence requirement for non-unknown primary service
    if primary_service != "unknown" and not primary_evidence:
        primary_service = "unknown"
        confidence = "unknown"
        if status == "qualified":
            status = "insufficient_data"

    additional: list[dict[str, Any]] = []
    for item in raw.get("additional_opportunities") or []:
        if not isinstance(item, dict):
            continue
        svc = str(item.get("service") or "").strip().lower()
        if svc not in ALLOWED_SERVICES or svc == "unknown":
            continue
        ev = item.get("evidence") or []
        if not isinstance(ev, list) or not any(str(x).strip() for x in ev):
            continue
        conf = str(item.get("confidence") or "unknown").strip().lower()
        if conf not in ALLOWED_CONFIDENCE:
            conf = "unknown"
        additional.append(
            {
                "service": svc,
                "confidence": conf,
                "reason": str(item.get("reason") or "").strip() or None,
                "evidence": [str(x).strip() for x in ev if str(x).strip()],
            }
        )

    insights_raw = raw.get("personalization_insights") or []
    if not isinstance(insights_raw, list):
        insights_raw = []
    insights = [str(x).strip() for x in insights_raw if str(x).strip()]

    if status == "insufficient_data":
        lead_score = lead_score  # keep factors but priority unknown
    if status in {"error"}:
        lead_score = None
        bf = wo = ao = ct = eq = None  # type: ignore[assignment]

    priority = priority_from_score(lead_score if status != "error" else None, status)

    reason = raw.get("primary_reason")
    if reason is not None:
        reason = str(reason).strip() or None

    action = raw.get("recommended_action")
    if action is not None:
        action = str(action).strip() or None

    summary = raw.get("qualification_summary")
    if summary is not None:
        summary = str(summary).strip() or None

    return QualificationResult(
        status=status,
        lead_score=lead_score if status != "error" else None,
        priority=priority,
        business_fit_score=bf if status != "error" else None,
        website_opportunity_score=wo if status != "error" else None,
        automation_opportunity_score=ao if status != "error" else None,
        contactability_score=ct if status != "error" else None,
        evidence_quality_score=eq if status != "error" else None,
        primary_service=primary_service if status != "error" else "unknown",
        primary_opportunity_confidence=confidence if status != "error" else "unknown",
        primary_reason=reason,
        primary_evidence=primary_evidence,
        additional_opportunities=additional,
        recommended_action=action,
        personalization_insights=insights,
        qualification_summary=summary,
        provider=provider_name,
        model=model,
        model_version=model_version,
        prompt_version=prompt_version,
        error_message=str(raw.get("error_message") or "").strip() or None,
    )


def unconfigured_result(prompt_version: str | None = None) -> QualificationResult:
    return QualificationResult(
        status="unconfigured",
        lead_score=None,
        priority="unknown",
        primary_service="unknown",
        primary_opportunity_confidence="unknown",
        primary_evidence=[],
        additional_opportunities=[],
        personalization_insights=[],
        provider="none",
        prompt_version=prompt_version,
        error_message="No AI provider configured",
    )


def error_result(
    message: str,
    *,
    provider_name: str,
    model: str | None = None,
    prompt_version: str | None = None,
) -> QualificationResult:
    return QualificationResult(
        status="error",
        priority="unknown",
        primary_service="unknown",
        primary_opportunity_confidence="unknown",
        provider=provider_name,
        model=model,
        prompt_version=prompt_version,
        error_message=message[:255],
    )
