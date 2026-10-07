"""Explainable deterministic website scoring — no invented metrics."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.website.crawler import CrawlResult
from app.services.website.html_signals import PageSignals


@dataclass
class ScoreResult:
    seo_score: int | None = None
    seo_checks: dict = field(default_factory=dict)
    mobile_score: int | None = None
    mobile_ready: bool | None = None
    accessibility_score: int | None = None
    performance_score: int | None = None  # Always None without PageSpeed
    website_score: int | None = None
    score_reasons: list[str] = field(default_factory=list)


def compute_scores(crawl: CrawlResult, signals: PageSignals) -> ScoreResult:
    result = ScoreResult()
    if not crawl.reachable or not crawl.pages:
        return result

    # SEO: transparent weights totaling 100
    seo_checks = {
        "title": {"pass": signals.has_title, "weight": 20},
        "meta_description": {"pass": signals.has_meta_description, "weight": 20},
        "h1": {"pass": signals.has_h1, "weight": 20},
        "canonical": {"pass": signals.has_canonical, "weight": 15},
        "viewport": {"pass": signals.has_viewport, "weight": 15},
        "alt_coverage": {
            "pass": _alt_pass(signals),
            "weight": 10,
            "detail": f"{signals.images_with_alt}/{signals.image_count}" if signals.image_count else "no images",
        },
    }
    seo_score = sum(c["weight"] for c in seo_checks.values() if c["pass"])
    result.seo_score = seo_score
    result.seo_checks = seo_checks

    # Mobile: viewport 60 + responsive hint 40
    mobile = 0
    if signals.has_viewport:
        mobile += 60
    if signals.responsive_css_hint:
        mobile += 40
    result.mobile_score = mobile
    result.mobile_ready = signals.has_viewport

    # Accessibility proxy: image alt coverage only when images exist
    if signals.image_count > 0:
        result.accessibility_score = int(round((signals.images_with_alt / signals.image_count) * 100))
    else:
        result.accessibility_score = None

    # performance_score intentionally null (no PageSpeed)
    result.performance_score = None

    reasons: list[str] = []
    if crawl.https_enabled:
        reasons.append("HTTPS enabled")
    else:
        reasons.append("HTTPS not detected on final URL")

    if signals.has_viewport:
        reasons.append("Good mobile viewport")
    else:
        reasons.append("Missing mobile viewport")

    if not signals.has_meta_description:
        reasons.append("Missing meta description")
    if not signals.has_clear_cta:
        reasons.append("Weak or missing clear CTA")
    else:
        reasons.append("Clear CTA detected")
    if not signals.has_booking:
        reasons.append("No online booking detected")
    else:
        reasons.append("Online booking signals detected")
    if signals.has_contact_form:
        reasons.append("Contact form detected")
    else:
        reasons.append("No contact form detected")
    if crawl.load_time_ms is not None:
        reasons.append(f"Homepage load time {crawl.load_time_ms}ms (timing only; not a PageSpeed score)")

    # Website quality score: weighted available components only
    components: list[tuple[str, int, int]] = []  # name, score, weight
    components.append(("seo", seo_score, 30))
    components.append(("mobile", mobile, 20))
    tech_health = 0
    tech_health += 25 if crawl.https_enabled else 0
    tech_health += 25 if crawl.http_status and 200 <= crawl.http_status < 400 else 0
    tech_health += 25 if signals.has_title else 0
    tech_health += 25 if signals.has_favicon else 0
    components.append(("technical", tech_health, 20))
    components.append(("cta", 100 if signals.has_clear_cta else 0, 10))
    contact = 0
    contact += 40 if signals.has_contact_form else 0
    contact += 30 if signals.has_phone or signals.has_email else 0
    contact += 30 if signals.has_clear_cta else 0
    components.append(("contact", contact, 10))
    components.append(("booking", 100 if signals.has_booking else 0, 10))

    total_weight = sum(w for _, _, w in components)
    if total_weight == 0:
        result.website_score = None
    else:
        weighted = sum(score * weight for _, score, weight in components)
        result.website_score = int(round(weighted / total_weight))

    result.score_reasons = reasons
    return result


def _alt_pass(signals: PageSignals) -> bool:
    if signals.image_count == 0:
        return True  # no images to fail
    return (signals.images_with_alt / signals.image_count) >= 0.5
