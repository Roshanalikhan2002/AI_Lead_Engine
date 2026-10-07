"""AI qualification provider abstraction — never invents qualifications without a provider."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Protocol

from app.core.config import Settings
from app.services.qualification.constants import QUALIFICATION_RESULT_JSON_SCHEMA
from app.services.qualification.normalize import (
    QualificationResult,
    error_result,
    normalize_provider_payload,
    unconfigured_result,
)
from app.services.qualification.prompt import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)


class AIQualificationProvider(Protocol):
    name: str

    def qualify_lead(self, input_data: dict[str, Any]) -> QualificationResult: ...


class UnconfiguredQualificationProvider:
    name = "none"

    def __init__(self, prompt_version: str = "v1.0"):
        self.prompt_version = prompt_version

    def qualify_lead(self, input_data: dict[str, Any]) -> QualificationResult:
        return unconfigured_result(self.prompt_version)


class MockQualificationProvider:
    """
    Deterministic offline/QA provider.
    NOT production AI — results are marked provider=mock.
    """

    name = "mock"

    def __init__(self, prompt_version: str = "v1.0"):
        self.prompt_version = prompt_version

    def qualify_lead(self, input_data: dict[str, Any]) -> QualificationResult:
        business = input_data.get("business") or {}
        website = input_data.get("website")
        det_ops = input_data.get("deterministic_opportunities") or []
        contacts = input_data.get("contacts") or []

        name = (business.get("name") or "").lower()
        if "error-case" in name or "force-error" in name:
            return error_result(
                "Mock provider error pattern",
                provider_name=self.name,
                model="mock-v1",
                prompt_version=self.prompt_version,
            )

        if website is None and not det_ops and not contacts:
            raw = {
                "status": "insufficient_data",
                "score_factors": {
                    "business_fit": 5,
                    "website_opportunity": 0,
                    "automation_opportunity": 0,
                    "contactability": 0,
                    "evidence_quality": 2,
                },
                "primary_service": "unknown",
                "primary_opportunity_confidence": "unknown",
                "primary_reason": None,
                "primary_evidence": [],
                "additional_opportunities": [],
                "recommended_action": None,
                "personalization_insights": _factual_insights(business, website, contacts),
                "qualification_summary": "Insufficient structured data to qualify this lead.",
            }
            return normalize_provider_payload(
                raw,
                provider_name=self.name,
                model="mock-v1",
                model_version="1",
                prompt_version=self.prompt_version,
            )

        # Prefer first deterministic opportunity with evidence
        primary = None
        for op in det_ops:
            if isinstance(op, dict) and op.get("service") and op.get("evidence"):
                primary = op
                break

        has_booking = None if website is None else website.get("has_booking")
        website_score = None if website is None else website.get("website_score")
        valid_contacts = sum(1 for c in contacts if (c or {}).get("verification_status") == "valid")

        if primary:
            service = str(primary.get("service"))
            evidence = [str(x) for x in (primary.get("evidence") or []) if str(x).strip()]
            conf = str(primary.get("confidence") or "medium")
            reason = primary.get("reason") or f"Potential {service.replace('_', ' ')} opportunity based on website signals."
        elif has_booking is False:
            service = "appointment_automation"
            evidence = ["No booking system detected"]
            if business.get("industry"):
                evidence.append(f"Business category is {business['industry']}")
            conf = "high"
            reason = "Potential appointment automation opportunity."
        elif website_score is not None and website_score < 55:
            service = "website_redesign"
            evidence = [f"Website score is {website_score}"]
            conf = "medium"
            reason = "Potential website redesign opportunity based on measured website score."
        elif contacts:
            service = "lead_capture"
            evidence = [f"{len(contacts)} public contact(s) discovered"]
            conf = "low"
            reason = "Limited automation signals; lead capture may be relevant."
        else:
            service = "unknown"
            evidence = []
            conf = "unknown"
            reason = None

        # Score factors from available facts only
        business_fit = 12
        if business.get("rating") is not None:
            business_fit += 6 if float(business["rating"]) >= 4.0 else 3
        if business.get("review_count"):
            business_fit += 4 if int(business["review_count"]) >= 50 else 2
        business_fit = min(25, business_fit)

        website_opp = 8
        if website is not None:
            if website_score is not None:
                website_opp = 22 if website_score < 50 else (16 if website_score < 70 else 10)
            if website.get("https_enabled") is False:
                website_opp = min(25, website_opp + 3)
        else:
            website_opp = 4

        automation = 6
        if has_booking is False:
            automation = 17
        elif website and website.get("has_chatbot") is False and website.get("has_contact_form"):
            automation = 12

        contactability = 4
        if contacts:
            contactability = 10
        if valid_contacts:
            contactability = 14
        contactability = min(15, contactability)

        evidence_quality = min(15, 6 + len(evidence) * 3 + (4 if det_ops else 0))

        status = "qualified" if service != "unknown" and evidence else "insufficient_data"
        if status == "insufficient_data":
            service = "unknown"
            conf = "unknown"

        additional = []
        for op in det_ops[1:3]:
            if not isinstance(op, dict):
                continue
            ev = [str(x) for x in (op.get("evidence") or []) if str(x).strip()]
            if not ev or not op.get("service"):
                continue
            if op.get("service") == service:
                continue
            additional.append(
                {
                    "service": op["service"],
                    "confidence": op.get("confidence") or "medium",
                    "reason": op.get("reason") or f"Potential {str(op['service']).replace('_', ' ')} opportunity.",
                    "evidence": ev,
                }
            )

        action = None
        if service != "unknown":
            action = (
                f"Review the potential {service.replace('_', ' ')} opportunity using the listed evidence "
                "before outreach."
            )

        raw = {
            "status": status,
            "score_factors": {
                "business_fit": business_fit,
                "website_opportunity": website_opp,
                "automation_opportunity": automation,
                "contactability": contactability,
                "evidence_quality": evidence_quality,
            },
            "primary_service": service,
            "primary_opportunity_confidence": conf,
            "primary_reason": reason,
            "primary_evidence": evidence,
            "additional_opportunities": additional,
            "recommended_action": action,
            "personalization_insights": _factual_insights(business, website, contacts),
            "qualification_summary": (
                f"Mock qualification for {business.get('name') or 'lead'} based only on supplied structured data."
            ),
        }
        return normalize_provider_payload(
            raw,
            provider_name=self.name,
            model="mock-v1",
            model_version="1",
            prompt_version=self.prompt_version,
        )


def _factual_insights(business: dict, website: dict | None, contacts: list) -> list[str]:
    insights: list[str] = []
    if business.get("rating") is not None and business.get("review_count") is not None:
        insights.append(
            f"Business has {business['rating']} rating with {business['review_count']} reviews."
        )
    elif business.get("rating") is not None:
        insights.append(f"Business rating is {business['rating']}.")
    if website and website.get("technology"):
        tech = website["technology"]
        if isinstance(tech, list) and tech:
            insights.append(f"Website technology signals include: {', '.join(str(t) for t in tech[:5])}.")
    if website and website.get("has_booking") is False:
        insights.append("Booking functionality was not detected.")
    if website and website.get("has_contact_form") is True:
        insights.append("Website has a contact form.")
    if contacts:
        insights.append(f"{len(contacts)} public email contact(s) were discovered.")
    return insights


class OpenAIQualificationProvider:
    """Official OpenAI client with JSON schema structured output."""

    name = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        prompt_version: str,
        api_url: str | None = None,
        max_tokens: int = 1200,
        timeout: float = 45.0,
        max_retries: int = 2,
        client=None,
    ):
        self.api_key = api_key
        self.model = model
        self.prompt_version = prompt_version
        self.api_url = (api_url or "").strip() or None
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.max_retries = max(0, min(5, max_retries))
        self._client = client

    def _get_client(self):
        if self._client is not None:
            return self._client
        from openai import OpenAI

        kwargs: dict[str, Any] = {"api_key": self.api_key, "timeout": self.timeout}
        if self.api_url:
            kwargs["base_url"] = self.api_url
        return OpenAI(**kwargs)

    def qualify_lead(self, input_data: dict[str, Any]) -> QualificationResult:
        client = self._get_client()
        user_prompt = build_user_prompt(input_data)
        delay = 0.5
        last_error = "AI provider unavailable"

        for attempt in range(self.max_retries + 1):
            try:
                response = client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": "ai_qualification_result",
                            "strict": True,
                            "schema": QUALIFICATION_RESULT_JSON_SCHEMA,
                        },
                    },
                    max_tokens=self.max_tokens,
                    temperature=0.1,
                )
                content = response.choices[0].message.content or ""
                try:
                    raw = json.loads(content)
                except json.JSONDecodeError:
                    return error_result(
                        "Malformed JSON from AI provider",
                        provider_name=self.name,
                        model=self.model,
                        prompt_version=self.prompt_version,
                    )
                return normalize_provider_payload(
                    raw,
                    provider_name=self.name,
                    model=self.model,
                    model_version=getattr(response, "model", None) or self.model,
                    prompt_version=self.prompt_version,
                )
            except Exception as exc:  # noqa: BLE001
                msg = str(exc).lower()
                # Never log API keys or full prompts
                logger.warning("OpenAI qualification attempt %s failed: %s", attempt + 1, type(exc).__name__)
                if "rate" in msg or "429" in msg:
                    last_error = "AI provider rate limited"
                elif "timeout" in msg:
                    last_error = "AI provider timeout"
                else:
                    last_error = "AI provider unavailable"
                if attempt >= self.max_retries:
                    break
                time.sleep(delay)
                delay = min(8.0, delay * 2)

        return error_result(
            last_error,
            provider_name=self.name,
            model=self.model,
            prompt_version=self.prompt_version,
        )


def get_qualification_provider(settings: Settings) -> AIQualificationProvider:
    name = (settings.ai_provider or "").strip().lower()
    prompt_version = settings.ai_prompt_version
    if not name or name in {"none", "off", "disabled"}:
        return UnconfiguredQualificationProvider(prompt_version=prompt_version)
    if name == "mock":
        return MockQualificationProvider(prompt_version=prompt_version)
    if name in {"openai", "gpt"}:
        key = (settings.ai_api_key or "").strip()
        if not key:
            return UnconfiguredQualificationProvider(prompt_version=prompt_version)
        return OpenAIQualificationProvider(
            api_key=key,
            model=settings.ai_model or "gpt-4o-mini",
            prompt_version=prompt_version,
            api_url=settings.ai_api_url or None,
            max_tokens=settings.ai_max_tokens,
            timeout=settings.ai_timeout_seconds,
            max_retries=settings.ai_max_retries,
        )
    # Unknown provider name → unconfigured (do not invent)
    return UnconfiguredQualificationProvider(prompt_version=prompt_version)
