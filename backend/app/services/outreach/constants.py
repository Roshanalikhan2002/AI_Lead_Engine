"""Constants and JSON schema for outreach generation."""

from __future__ import annotations

MAX_BODY_WORDS = 150
BANNED_SUBJECT_TERMS = frozenset(
    {
        "urgent",
        "final notice",
        "you need this",
        "free offer",
        "100% guaranteed",
        "guaranteed",
        "act now",
        "limited time",
    }
)

FABRICATED_CLAIM_PATTERNS = (
    "increased revenue",
    "saved 30 hours",
    "boosted conversions",
    "helped 100 companies",
    "struggling to manage",
    "customers are leaving",
    "looking to increase revenue",
    "unable to book appointments",
    "losing customers",
)

OUTREACH_RESULT_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "status": {
            "type": "string",
            "enum": ["generated", "insufficient_data", "error"],
        },
        "subjects": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "maxItems": 3,
        },
        "body": {"type": ["string", "null"]},
        "service": {"type": ["string", "null"]},
        "personalization_points": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["status", "subjects", "body", "service", "personalization_points"],
}
