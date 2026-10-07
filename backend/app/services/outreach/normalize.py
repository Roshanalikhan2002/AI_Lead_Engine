"""Validate / normalize outreach generation payloads."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.services.outreach.constants import (
    BANNED_SUBJECT_TERMS,
    FABRICATED_CLAIM_PATTERNS,
    MAX_BODY_WORDS,
)


@dataclass
class OutreachGenerationResult:
    status: str  # generated | insufficient_data | error | unconfigured
    subjects: list[str] = field(default_factory=list)
    body: str | None = None
    service: str | None = None
    personalization_points: list[str] = field(default_factory=list)
    provider: str = "none"
    model: str | None = None
    model_version: str | None = None
    prompt_version: str | None = None
    error_message: str | None = None


def word_count(text: str | None) -> int:
    if not text:
        return 0
    return len(re.findall(r"\b\w+\b", text))


def _clean_subjects(subjects: list[Any]) -> list[str]:
    cleaned: list[str] = []
    for s in subjects:
        text = str(s or "").strip()
        if not text:
            continue
        lower = text.lower()
        if any(term in lower for term in BANNED_SUBJECT_TERMS):
            continue
        cleaned.append(text[:255])
        if len(cleaned) >= 3:
            break
    return cleaned


def _body_has_fabricated_claims(body: str) -> bool:
    lower = body.lower()
    return any(p in lower for p in FABRICATED_CLAIM_PATTERNS)


def normalize_outreach_payload(
    raw: dict[str, Any],
    *,
    provider_name: str,
    expected_service: str | None,
    model: str | None = None,
    model_version: str | None = None,
    prompt_version: str | None = None,
) -> OutreachGenerationResult:
    if not isinstance(raw, dict):
        return OutreachGenerationResult(
            status="error",
            provider=provider_name,
            model=model,
            model_version=model_version,
            prompt_version=prompt_version,
            error_message="Malformed provider response",
        )

    status = str(raw.get("status") or "error").strip().lower()
    if status not in {"generated", "insufficient_data", "error"}:
        status = "error"

    subjects = _clean_subjects(list(raw.get("subjects") or []))
    body = raw.get("body")
    body = str(body).strip() if body is not None else None
    if body == "":
        body = None

    service = raw.get("service")
    service = str(service).strip().lower() if service else None
    if expected_service and expected_service != "unknown":
        service = expected_service
    elif service == "unknown":
        service = None

    points_raw = raw.get("personalization_points") or []
    if not isinstance(points_raw, list):
        points_raw = []
    points = [str(x).strip() for x in points_raw if str(x).strip()]

    if status == "generated":
        if not subjects or not body:
            status = "error"
            return OutreachGenerationResult(
                status="error",
                provider=provider_name,
                model=model,
                prompt_version=prompt_version,
                error_message="Missing subject or body",
            )
        if word_count(body) > MAX_BODY_WORDS:
            # Soft trim by sentences isn't required — reject for quality
            status = "error"
            return OutreachGenerationResult(
                status="error",
                subjects=subjects,
                body=body,
                service=service,
                personalization_points=points,
                provider=provider_name,
                model=model,
                prompt_version=prompt_version,
                error_message=f"Body exceeds {MAX_BODY_WORDS} words",
            )
        if _body_has_fabricated_claims(body):
            return OutreachGenerationResult(
                status="error",
                subjects=subjects,
                body=body,
                service=service,
                personalization_points=points,
                provider=provider_name,
                model=model,
                prompt_version=prompt_version,
                error_message="Body contains unsupported claims",
            )
        if not points:
            return OutreachGenerationResult(
                status="error",
                subjects=subjects,
                body=body,
                service=service,
                provider=provider_name,
                model=model,
                prompt_version=prompt_version,
                error_message="Missing personalization points",
            )

    return OutreachGenerationResult(
        status=status,
        subjects=subjects,
        body=body,
        service=service,
        personalization_points=points,
        provider=provider_name,
        model=model,
        model_version=model_version,
        prompt_version=prompt_version,
        error_message=str(raw.get("error_message") or "").strip() or None,
    )


def unconfigured_result(prompt_version: str | None = None) -> OutreachGenerationResult:
    return OutreachGenerationResult(
        status="unconfigured",
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
) -> OutreachGenerationResult:
    return OutreachGenerationResult(
        status="error",
        provider=provider_name,
        model=model,
        prompt_version=prompt_version,
        error_message=message[:255],
    )


def insufficient_result(
    message: str,
    *,
    provider_name: str = "none",
    prompt_version: str | None = None,
) -> OutreachGenerationResult:
    return OutreachGenerationResult(
        status="insufficient_data",
        provider=provider_name,
        prompt_version=prompt_version,
        error_message=message[:255],
    )
