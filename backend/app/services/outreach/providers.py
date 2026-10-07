"""Outreach generation provider abstraction — drafts only, never sends."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Protocol

from app.core.config import Settings
from app.services.outreach.constants import OUTREACH_RESULT_JSON_SCHEMA
from app.services.outreach.normalize import (
    OutreachGenerationResult,
    error_result,
    normalize_outreach_payload,
    unconfigured_result,
)
from app.services.outreach.prompt import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)


class OutreachGenerationProvider(Protocol):
    name: str

    def generate_email(self, context: dict[str, Any]) -> OutreachGenerationResult: ...


class UnconfiguredOutreachProvider:
    name = "none"

    def __init__(self, prompt_version: str = "v1.0"):
        self.prompt_version = prompt_version

    def generate_email(self, context: dict[str, Any]) -> OutreachGenerationResult:
        return unconfigured_result(self.prompt_version)


class MockOutreachProvider:
    """Deterministic offline/QA provider — NOT production AI."""

    name = "mock"

    def __init__(self, prompt_version: str = "v1.0", agency_name: str = "LeadFlow AI"):
        self.prompt_version = prompt_version
        self.agency_name = agency_name

    def generate_email(self, context: dict[str, Any]) -> OutreachGenerationResult:
        business = context.get("business") or {}
        website = context.get("website") or {}
        qualification = context.get("qualification") or {}
        name = business.get("name") or "your team"
        service = qualification.get("primary_service") or "unknown"

        if "error-case" in str(name).lower():
            return error_result(
                "Mock outreach error pattern",
                provider_name=self.name,
                model="mock-outreach-v1",
                prompt_version=self.prompt_version,
            )

        if not qualification or service in {None, "unknown"}:
            return normalize_outreach_payload(
                {
                    "status": "insufficient_data",
                    "subjects": [],
                    "body": None,
                    "service": None,
                    "personalization_points": [],
                },
                provider_name=self.name,
                expected_service=None,
                model="mock-outreach-v1",
                model_version="1",
                prompt_version=self.prompt_version,
            )

        evidence = list(qualification.get("evidence") or [])
        points: list[str] = []
        for e in evidence[:4]:
            points.append(str(e))
        if website.get("has_booking") is False and "booking" not in " ".join(points).lower():
            points.append("No booking system detected")
        if website.get("has_contact_form") is True:
            points.append("Contact form detected")
        if business.get("rating") is not None and business.get("review_count") is not None:
            points.append(
                f"Business has {business['rating']} rating with {business['review_count']} reviews"
            )
        if website.get("technology"):
            tech = website["technology"]
            if isinstance(tech, list) and tech:
                points.append(f"Website technology signals include {tech[0]}")

        # Evidence-based observation wording (careful, not fabricated)
        observation = "I reviewed publicly available website signals for your business."
        if website.get("has_booking") is False:
            observation = (
                "I couldn't find an online booking option on the website, "
                "though a contact path appears available."
                if website.get("has_contact_form")
                else "I couldn't find an online booking option on the website."
            )
        elif website.get("website_score") is not None:
            observation = (
                f"I noticed measured website signals including a website score of "
                f"{website['website_score']}."
            )

        service_label = str(service).replace("_", " ")
        body = (
            f"Hi {name} team,\n\n"
            f"{observation}\n\n"
            f"We help businesses explore potential {service_label} improvements based on "
            f"those website signals. If this is something you may be considering, "
            f"I'd be happy to walk through a lightweight option that fits your current setup.\n\n"
            f"Would a quick 15-minute conversation next week make sense?\n\n"
            f"Best,\n{self.agency_name}"
        )

        subjects = [
            f"Quick idea for {name}",
            f"Website opportunity for {name}",
            f"Quick idea about your booking flow" if website.get("has_booking") is False else f"Idea for {name}",
        ]

        return normalize_outreach_payload(
            {
                "status": "generated",
                "subjects": subjects,
                "body": body,
                "service": service,
                "personalization_points": points[:5],
            },
            provider_name=self.name,
            expected_service=service,
            model="mock-outreach-v1",
            model_version="1",
            prompt_version=self.prompt_version,
        )


class OpenAIOutreachProvider:
    name = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        prompt_version: str,
        agency_name: str = "LeadFlow AI",
        api_url: str | None = None,
        max_tokens: int = 900,
        timeout: float = 45.0,
        max_retries: int = 2,
        client=None,
    ):
        self.api_key = api_key
        self.model = model
        self.prompt_version = prompt_version
        self.agency_name = agency_name
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

    def generate_email(self, context: dict[str, Any]) -> OutreachGenerationResult:
        client = self._get_client()
        user_prompt = build_user_prompt(context, self.agency_name)
        expected = (context.get("qualification") or {}).get("primary_service")
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
                            "name": "outreach_draft_result",
                            "strict": True,
                            "schema": OUTREACH_RESULT_JSON_SCHEMA,
                        },
                    },
                    max_tokens=self.max_tokens,
                    temperature=0.3,
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
                return normalize_outreach_payload(
                    raw,
                    provider_name=self.name,
                    expected_service=expected,
                    model=self.model,
                    model_version=getattr(response, "model", None) or self.model,
                    prompt_version=self.prompt_version,
                )
            except Exception as exc:  # noqa: BLE001
                msg = str(exc).lower()
                logger.warning("OpenAI outreach attempt %s failed: %s", attempt + 1, type(exc).__name__)
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


def get_outreach_provider(settings: Settings) -> OutreachGenerationProvider:
    name = (settings.ai_provider or "").strip().lower()
    prompt_version = settings.outreach_prompt_version
    agency = settings.agency_name
    if not name or name in {"none", "off", "disabled"}:
        return UnconfiguredOutreachProvider(prompt_version=prompt_version)
    if name == "mock":
        return MockOutreachProvider(prompt_version=prompt_version, agency_name=agency)
    if name in {"openai", "gpt"}:
        key = (settings.ai_api_key or "").strip()
        if not key:
            return UnconfiguredOutreachProvider(prompt_version=prompt_version)
        return OpenAIOutreachProvider(
            api_key=key,
            model=settings.ai_model or "gpt-4o-mini",
            prompt_version=prompt_version,
            agency_name=agency,
            api_url=settings.ai_api_url or None,
            max_tokens=settings.outreach_max_tokens,
            timeout=settings.ai_timeout_seconds,
            max_retries=settings.ai_max_retries,
        )
    return UnconfiguredOutreachProvider(prompt_version=prompt_version)
