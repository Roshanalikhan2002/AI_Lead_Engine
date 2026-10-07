"""Deterministic public email extraction and classification — never invents emails."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup

from app.utils.normalize import normalize_domain

EMAIL_RE = re.compile(
    r"\b([a-zA-Z0-9](?:[a-zA-Z0-9._%+\-]{0,62}[a-zA-Z0-9])?)@([a-zA-Z0-9](?:[a-zA-Z0-9.\-]{0,251}[a-zA-Z0-9])?\.[a-zA-Z]{2,})\b"
)

OBFUSCATED_RE = re.compile(
    r"\b([a-zA-Z0-9][a-zA-Z0-9._%+\-]{0,62})\s*(?:\[at\]|\(at\)|\sat\s)\s*"
    r"([a-zA-Z0-9][a-zA-Z0-9.\-]{0,250})\s*(?:\[dot\]|\(dot\)|\sdot\s|\.)\s*"
    r"([a-zA-Z]{2,})\b",
    re.IGNORECASE,
)

PLACEHOLDER_LOCALS = {
    "example",
    "email",
    "name",
    "user",
    "test",
    "sample",
    "yourname",
    "you",
    "domain",
    "username",
    "firstname",
    "lastname",
}

PLACEHOLDER_DOMAINS = {
    "example.com",
    "example.org",
    "example.net",
    "domain.com",
    "email.com",
    "test.com",
    "localhost",
    "sentry.io",
    "wixpress.com",
    "schema.org",
    "w3.org",
    "googleapis.com",
}

GENERIC_PREFIX = {
    "info": "business",
    "hello": "business",
    "contact": "business",
    "office": "business",
    "admin": "business",
    "enquiries": "business",
    "inquiry": "business",
    "inquiries": "business",
    "mail": "business",
    "general": "business",
    "sales": "sales",
    "support": "support",
    "help": "support",
    "service": "support",
    "customerservice": "support",
    "marketing": "marketing",
    "press": "marketing",
    "media": "marketing",
    "booking": "booking",
    "bookings": "booking",
    "appointments": "booking",
    "appointment": "booking",
    "reserve": "booking",
    "reservations": "booking",
}


@dataclass
class ExtractedEmail:
    email: str
    normalized_email: str
    source_url: str
    extraction_method: str  # mailto | visible | obfuscated
    page_kind: str  # contact | about | team | home | other


def classify_page_kind(url: str) -> str:
    path = (urlparse(url).path or "/").lower()
    if any(x in path for x in ("/contact", "contact-us", "get-in-touch")):
        return "contact"
    if any(x in path for x in ("/about", "/our-story")):
        return "about"
    if any(x in path for x in ("/team", "/staff", "/people", "/our-team")):
        return "team"
    if any(x in path for x in ("/support", "/help")):
        return "support"
    if any(x in path for x in ("/book", "/booking", "/schedule", "/appointment")):
        return "booking"
    if path in {"", "/"} or path.count("/") <= 1:
        return "home"
    return "other"


def extract_emails_from_html(html: str, source_url: str) -> list[ExtractedEmail]:
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    page_kind = classify_page_kind(source_url)
    found: dict[str, ExtractedEmail] = {}

    for a in soup.find_all("a", href=True):
        href = unquote(a["href"]).strip()
        if href.lower().startswith("mailto:"):
            raw = href[7:].split("?")[0].strip()
            _add(found, raw, source_url, "mailto", page_kind)

    # Prefer footer/contact sections text, but also scan full visible text
    texts: list[str] = []
    for selector in ("footer", "[class*=contact]", "[id*=contact]", "main", "body"):
        for node in soup.select(selector):
            texts.append(node.get_text(" ", strip=True))
    if not texts:
        texts.append(soup.get_text(" ", strip=True))

    blob = "\n".join(texts)
    for match in EMAIL_RE.finditer(blob):
        _add(found, match.group(0), source_url, "visible", page_kind)

    for match in OBFUSCATED_RE.finditer(blob):
        reconstructed = f"{match.group(1)}@{match.group(2)}.{match.group(3)}"
        _add(found, reconstructed, source_url, "obfuscated", page_kind)

    return list(found.values())


def _add(
    bucket: dict[str, ExtractedEmail],
    raw: str,
    source_url: str,
    method: str,
    page_kind: str,
) -> None:
    normalized = normalize_email(raw)
    if not normalized:
        return
    # Prefer mailto over visible over obfuscated
    priority = {"mailto": 3, "visible": 2, "obfuscated": 1}
    existing = bucket.get(normalized)
    if existing and priority.get(existing.extraction_method, 0) >= priority.get(method, 0):
        # Prefer contact page evidence when methods equal-ish
        if existing.page_kind == "contact" or page_kind != "contact":
            return
    bucket[normalized] = ExtractedEmail(
        email=normalized,
        normalized_email=normalized,
        source_url=source_url,
        extraction_method=method,
        page_kind=page_kind,
    )


def normalize_email(raw: str | None) -> str | None:
    if not raw:
        return None
    value = unquote(raw).strip().lower().strip(".,;:()<>[]\"'")
    if value.startswith("mailto:"):
        value = value[7:]
    value = value.split("?")[0].strip()
    if not EMAIL_RE.fullmatch(value):
        return None
    if not is_plausible_email(value):
        return None
    return value


def is_plausible_email(email: str) -> bool:
    try:
        local, domain = email.split("@", 1)
    except ValueError:
        return False
    if not local or not domain or "." not in domain:
        return False
    if local in PLACEHOLDER_LOCALS:
        return False
    if domain in PLACEHOLDER_DOMAINS or domain.endswith(".local") or domain.endswith(".test"):
        return False
    if domain in {"localhost", "127.0.0.1"}:
        return False
    # Reject image / asset looking locals
    if any(local.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".js")):
        return False
    if "javascript" in local or local.startswith("{"):
        return False
    if ".." in email or email.startswith(".") or email.endswith("."):
        return False
    return True


def classify_contact_type(email: str) -> str:
    local = email.split("@", 1)[0].lower()
    local_key = local.replace(".", "").replace("-", "").replace("_", "")
    if local in GENERIC_PREFIX:
        return GENERIC_PREFIX[local]
    if local_key in GENERIC_PREFIX:
        return GENERIC_PREFIX[local_key]
    # personal-ish if looks like first.last
    if re.fullmatch(r"[a-z]+(?:[._-][a-z]+){1,2}", local) and local not in GENERIC_PREFIX:
        return "personal"
    return "unknown"


def guess_contact_name(email: str) -> str | None:
    local = email.split("@", 1)[0].lower()
    if classify_contact_type(email) != "personal":
        return None
    if not re.fullmatch(r"[a-z]+(?:[._-][a-z]+){1,2}", local):
        return None
    parts = re.split(r"[._-]+", local)
    if len(parts) < 2 or any(len(p) < 2 for p in parts):
        return None
    if any(p in PLACEHOLDER_LOCALS for p in parts):
        return None
    return " ".join(p.capitalize() for p in parts)


def domains_match(email: str, website: str | None) -> bool:
    email_domain = email.split("@", 1)[1].lower()
    site_domain = normalize_domain(website)
    if not site_domain:
        return False
    email_domain = email_domain[4:] if email_domain.startswith("www.") else email_domain
    site_domain = site_domain[4:] if site_domain.startswith("www.") else site_domain
    return email_domain == site_domain or email_domain.endswith("." + site_domain) or site_domain.endswith(
        "." + email_domain
    )


def source_label(page_kind: str, method: str) -> str:
    page_map = {
        "contact": "website_contact_page",
        "about": "website_about_page",
        "team": "website_team_page",
        "support": "website_support_page",
        "booking": "website_booking_page",
        "home": "website_homepage",
        "other": "website",
    }
    base = page_map.get(page_kind, "website")
    if method == "mailto":
        return base
    if method == "obfuscated":
        return f"{base}_obfuscated"
    return base


def compute_confidence(
    *,
    method: str,
    page_kind: str,
    domain_match: bool,
) -> str:
    score = 0
    if method == "mailto":
        score += 40
    elif method == "visible":
        score += 25
    else:
        score += 10

    if page_kind == "contact":
        score += 30
    elif page_kind in {"about", "team", "support", "booking"}:
        score += 20
    elif page_kind == "home":
        score += 10

    if domain_match:
        score += 30
    else:
        score += 5

    if score >= 80:
        return "high"
    if score >= 50:
        return "medium"
    return "low"


def pick_primary(contacts: list[dict]) -> str | None:
    """Return normalized_email that should be primary."""
    if not contacts:
        return None
    order = {"sales": 0, "business": 1, "booking": 2, "support": 3, "marketing": 4, "personal": 5, "unknown": 6}
    conf = {"high": 0, "medium": 1, "low": 2}
    ranked = sorted(
        contacts,
        key=lambda c: (
            0 if c.get("domain_match") else 1,
            conf.get(c.get("confidence", "low"), 9),
            order.get(c.get("contact_type", "unknown"), 9),
            c.get("normalized_email", ""),
        ),
    )
    return ranked[0]["normalized_email"]
