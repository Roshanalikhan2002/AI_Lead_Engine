"""Central SaaS plan registry — limits & features (not hardcoded in routes)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.config import get_settings


@dataclass(frozen=True)
class PlanDefinition:
    id: str
    name: str
    description: str
    monthly_price: float | None  # None = Contact Sales / custom
    annual_price: float | None
    currency: str
    # None = unlimited
    limits: dict[str, int | None]
    features: set[str]
    hard_limit: bool = True


# Resource keys used by UsageService
USAGE_RESOURCES = (
    "leads_discovered",
    "website_analyses",
    "emails_discovered",
    "emails_verified",
    "ai_qualifications",
    "ai_generations",
    "ai_reply_classifications",
    "ai_reply_suggestions",
    "emails_sent",
    "meetings_booked",
)

# Seat / capacity limits (not period counters)
CAPACITY_RESOURCES = (
    "team_members",
    "active_campaigns",
    "campaign_recipients",
)

FEATURES = (
    "ai_qualification",
    "ai_outreach",
    "campaigns",
    "reply_intelligence",
    "meetings",
    "advanced_analytics",
)


def _prices() -> dict[str, tuple[float | None, float | None]]:
    s = get_settings()
    return {
        "free": (0.0, 0.0),
        "starter": (s.plan_price_starter_monthly, s.plan_price_starter_annual),
        "growth": (s.plan_price_growth_monthly, s.plan_price_growth_annual),
        "agency": (s.plan_price_agency_monthly, s.plan_price_agency_annual),
        "enterprise": (None, None),
    }


def get_plan_registry() -> dict[str, PlanDefinition]:
    prices = _prices()
    currency = get_settings().plan_currency or "USD"

    return {
        "free": PlanDefinition(
            id="free",
            name="Free",
            description="Get started without a payment provider.",
            monthly_price=prices["free"][0],
            annual_price=prices["free"][1],
            currency=currency,
            limits={
                "leads_discovered": 100,
                "website_analyses": 50,
                "emails_discovered": 50,
                "emails_verified": 50,
                "ai_qualifications": 25,
                "ai_generations": 25,
                "ai_reply_classifications": 50,
                "ai_reply_suggestions": 25,
                "emails_sent": 25,
                "meetings_booked": 10,
                "team_members": 2,
                "active_campaigns": 1,
                "campaign_recipients": 50,
            },
            features={
                "ai_qualification",
                "ai_outreach",
                "campaigns",
                "reply_intelligence",
                "meetings",
            },
            hard_limit=True,
        ),
        "starter": PlanDefinition(
            id="starter",
            name="Starter",
            description="For small agencies ramping outbound.",
            monthly_price=prices["starter"][0],
            annual_price=prices["starter"][1],
            currency=currency,
            limits={
                "leads_discovered": 1000,
                "website_analyses": 500,
                "emails_discovered": 500,
                "emails_verified": 500,
                "ai_qualifications": 250,
                "ai_generations": 250,
                "ai_reply_classifications": 500,
                "ai_reply_suggestions": 250,
                "emails_sent": 500,
                "meetings_booked": 100,
                "team_members": 5,
                "active_campaigns": 5,
                "campaign_recipients": 500,
            },
            features={
                "ai_qualification",
                "ai_outreach",
                "campaigns",
                "reply_intelligence",
                "meetings",
            },
            hard_limit=True,
        ),
        "growth": PlanDefinition(
            id="growth",
            name="Growth",
            description="Higher volume for scaling teams.",
            monthly_price=prices["growth"][0],
            annual_price=prices["growth"][1],
            currency=currency,
            limits={
                "leads_discovered": 5000,
                "website_analyses": 2500,
                "emails_discovered": 2500,
                "emails_verified": 2500,
                "ai_qualifications": 1000,
                "ai_generations": 1000,
                "ai_reply_classifications": 2000,
                "ai_reply_suggestions": 1000,
                "emails_sent": 2500,
                "meetings_booked": 500,
                "team_members": 15,
                "active_campaigns": 20,
                "campaign_recipients": 5000,
            },
            features={
                "ai_qualification",
                "ai_outreach",
                "campaigns",
                "reply_intelligence",
                "meetings",
                "advanced_analytics",
            },
            hard_limit=True,
        ),
        "agency": PlanDefinition(
            id="agency",
            name="Agency",
            description="Multi-client agency capacity.",
            monthly_price=prices["agency"][0],
            annual_price=prices["agency"][1],
            currency=currency,
            limits={
                "leads_discovered": 25000,
                "website_analyses": 10000,
                "emails_discovered": 10000,
                "emails_verified": 10000,
                "ai_qualifications": 5000,
                "ai_generations": 5000,
                "ai_reply_classifications": 10000,
                "ai_reply_suggestions": 5000,
                "emails_sent": 10000,
                "meetings_booked": 2000,
                "team_members": 50,
                "active_campaigns": 100,
                "campaign_recipients": 25000,
            },
            features={
                "ai_qualification",
                "ai_outreach",
                "campaigns",
                "reply_intelligence",
                "meetings",
                "advanced_analytics",
            },
            hard_limit=True,
        ),
        "enterprise": PlanDefinition(
            id="enterprise",
            name="Enterprise",
            description="Custom limits and commercial terms.",
            monthly_price=None,
            annual_price=None,
            currency=currency,
            limits={
                "leads_discovered": None,
                "website_analyses": None,
                "emails_discovered": None,
                "emails_verified": None,
                "ai_qualifications": None,
                "ai_generations": None,
                "ai_reply_classifications": None,
                "ai_reply_suggestions": None,
                "emails_sent": None,
                "meetings_booked": None,
                "team_members": None,
                "active_campaigns": None,
                "campaign_recipients": None,
            },
            features={
                "ai_qualification",
                "ai_outreach",
                "campaigns",
                "reply_intelligence",
                "meetings",
                "advanced_analytics",
            },
            hard_limit=False,
        ),
    }


def get_plan(plan_id: str) -> PlanDefinition:
    registry = get_plan_registry()
    key = (plan_id or "free").strip().lower()
    return registry.get(key, registry["free"])


def list_plans_public() -> list[dict[str, Any]]:
    out = []
    for plan in get_plan_registry().values():
        out.append(
            {
                "id": plan.id,
                "name": plan.name,
                "description": plan.description,
                "monthly_price": plan.monthly_price,
                "annual_price": plan.annual_price,
                "currency": plan.currency,
                "limits": plan.limits,
                "features": sorted(plan.features),
                "contact_sales": plan.monthly_price is None,
            }
        )
    return out
