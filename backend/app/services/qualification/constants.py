"""Shared constants for AI qualification."""

from __future__ import annotations

ALLOWED_SERVICES = frozenset(
    {
        "website_development",
        "website_redesign",
        "appointment_automation",
        "ai_chatbot",
        "lead_capture",
        "ecommerce_development",
        "custom_software",
        "other",
        "unknown",
    }
)

ALLOWED_STATUSES = frozenset(
    {"qualified", "not_qualified", "insufficient_data", "error", "unconfigured"}
)

ALLOWED_PRIORITIES = frozenset({"hot", "warm", "cold", "unknown"})
ALLOWED_CONFIDENCE = frozenset({"high", "medium", "low", "unknown"})

SCORE_CAPS = {
    "business_fit": 25,
    "website_opportunity": 25,
    "automation_opportunity": 20,
    "contactability": 15,
    "evidence_quality": 15,
}

_SERVICE_ENUM = sorted(ALLOWED_SERVICES)

QUALIFICATION_RESULT_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "status": {
            "type": "string",
            "enum": ["qualified", "not_qualified", "insufficient_data", "error"],
        },
        "score_factors": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "business_fit": {"type": "integer"},
                "website_opportunity": {"type": "integer"},
                "automation_opportunity": {"type": "integer"},
                "contactability": {"type": "integer"},
                "evidence_quality": {"type": "integer"},
            },
            "required": [
                "business_fit",
                "website_opportunity",
                "automation_opportunity",
                "contactability",
                "evidence_quality",
            ],
        },
        "primary_service": {"type": "string", "enum": _SERVICE_ENUM},
        "primary_opportunity_confidence": {
            "type": "string",
            "enum": ["high", "medium", "low", "unknown"],
        },
        "primary_reason": {"type": ["string", "null"]},
        "primary_evidence": {"type": "array", "items": {"type": "string"}},
        "additional_opportunities": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "service": {"type": "string", "enum": _SERVICE_ENUM},
                    "confidence": {
                        "type": "string",
                        "enum": ["high", "medium", "low", "unknown"],
                    },
                    "reason": {"type": "string"},
                    "evidence": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["service", "confidence", "reason", "evidence"],
            },
        },
        "recommended_action": {"type": ["string", "null"]},
        "personalization_insights": {"type": "array", "items": {"type": "string"}},
        "qualification_summary": {"type": ["string", "null"]},
    },
    "required": [
        "status",
        "score_factors",
        "primary_service",
        "primary_opportunity_confidence",
        "primary_reason",
        "primary_evidence",
        "additional_opportunities",
        "recommended_action",
        "personalization_insights",
        "qualification_summary",
    ],
}
