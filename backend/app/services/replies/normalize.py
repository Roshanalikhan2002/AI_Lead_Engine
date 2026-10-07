"""Normalize and validate reply classification payloads."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.replies.constants import ALLOWED_INTENTS, ALLOWED_SENTIMENTS, ALLOWED_URGENCIES


@dataclass
class ClassificationResult:
    intent: str = "unknown"
    intent_confidence: float | None = None
    sentiment: str = "unknown"
    sentiment_confidence: float | None = None
    urgency: str = "unknown"
    requires_human: bool = True
    reason: str | None = None
    evidence: list[str] = field(default_factory=list)
    provider: str = "none"
    model: str | None = None
    model_version: str | None = None
    prompt_version: str | None = None
    error: str | None = None


def _clamp_conf(value: Any) -> float | None:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, v))


def normalize_classification_payload(
    payload: dict[str, Any] | None,
    *,
    provider_name: str,
    model: str | None = None,
    model_version: str | None = None,
    prompt_version: str | None = None,
) -> ClassificationResult:
    data = payload or {}
    intent = str(data.get("intent") or "unknown").strip().lower()
    if intent not in ALLOWED_INTENTS:
        intent = "unknown"
    sentiment = str(data.get("sentiment") or "unknown").strip().lower()
    if sentiment not in ALLOWED_SENTIMENTS:
        sentiment = "unknown"
    urgency = str(data.get("urgency") or "unknown").strip().lower()
    if urgency not in ALLOWED_URGENCIES:
        urgency = "unknown"

    evidence_raw = data.get("evidence") or []
    evidence: list[str] = []
    if isinstance(evidence_raw, list):
        for item in evidence_raw[:8]:
            text = str(item).strip()
            if text:
                evidence.append(text[:300])

    requires_human = bool(data.get("requires_human", True))
    if intent in {"question", "pricing_question", "needs_information", "unknown", "other", "wrong_contact"}:
        requires_human = True
    if intent in {"unsubscribe", "not_interested", "out_of_office", "automatic_reply"}:
        # Still may need human for complaint; unsubscribe is auto-handled
        requires_human = intent not in {"unsubscribe", "out_of_office", "automatic_reply"}

    return ClassificationResult(
        intent=intent,
        intent_confidence=_clamp_conf(data.get("intent_confidence")),
        sentiment=sentiment,
        sentiment_confidence=_clamp_conf(data.get("sentiment_confidence")),
        urgency=urgency,
        requires_human=requires_human,
        reason=(str(data.get("reason")).strip()[:1000] if data.get("reason") else None),
        evidence=evidence,
        provider=provider_name,
        model=model,
        model_version=model_version,
        prompt_version=prompt_version,
    )


@dataclass
class SuggestionResult:
    subject: str | None = None
    body: str = ""
    provider: str = "none"
    model: str | None = None
    model_version: str | None = None
    prompt_version: str | None = None
    error: str | None = None
    status: str = "ok"  # ok | insufficient_data | error | unconfigured
