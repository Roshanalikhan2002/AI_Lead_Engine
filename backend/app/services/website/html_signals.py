"""Deterministic HTML signal extraction — evidence only, no LLM."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from app.services.website.crawler import CrawlResult, FetchedPage

PHONE_RE = re.compile(
    r"(?:\+?\d{1,3}[\s\-.]?)?(?:\(?\d{3}\)?[\s\-.]?)\d{3}[\s\-.]?\d{4}"
)
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

CTA_PHRASES = [
    "book now",
    "get started",
    "contact us",
    "request quote",
    "request a quote",
    "schedule appointment",
    "schedule an appointment",
    "call now",
    "shop now",
    "book appointment",
    "free consultation",
]

BOOKING_HREF_HINTS = (
    "book",
    "booking",
    "appointment",
    "schedule",
    "reserve",
    "reservation",
    "calendly",
    "acuity",
    "setmore",
    "simplybook",
    "squareup.com/appointments",
)

BOOKING_PROVIDERS = (
    "calendly.com",
    "acuityscheduling.com",
    "square.site",
    "setmore.com",
    "simplybook.me",
    "mindbodyonline.com",
    "booksy.com",
)

CHATBOT_SIGNATURES = {
    "intercom": ["intercom", "widget.intercom.io"],
    "drift": ["js.driftt.com", "drift.com"],
    "tawk": ["embed.tawk.to", "tawk.to"],
    "hubspot": ["js.hs-scripts.com", "hubspot"],
    "zendesk": ["static.zdassets.com", "zopim"],
    "crisp": ["client.crisp.chat", "crisp.chat"],
    "manychat": ["manychat"],
    "livechat": ["cdn.livechatinc.com", "livechat"],
    "tidio": ["code.tidio.co"],
    "facebook": ["facebook.com/customer_chat"],
}

TECH_SIGNATURES = {
    "WordPress": ["wp-content", "wp-includes", "wordpress"],
    "Shopify": ["cdn.shopify.com", "Shopify.theme"],
    "Wix": ["static.wixstatic.com", "wix.com"],
    "Webflow": ["assets.website-files.com", "webflow"],
    "Squarespace": ["squarespace.com", "static.squarespace"],
    "WooCommerce": ["woocommerce", "wp-content/plugins/woocommerce"],
}


@dataclass
class PageSignals:
    has_title: bool = False
    title_text: str | None = None
    has_meta_description: bool = False
    has_h1: bool = False
    has_favicon: bool = False
    has_canonical: bool = False
    has_viewport: bool = False
    image_count: int = 0
    images_with_alt: int = 0
    internal_link_count: int = 0
    external_link_count: int = 0
    has_contact_form: bool = False
    has_booking: bool = False
    booking_evidence: list[str] = field(default_factory=list)
    has_chatbot: bool = False
    chatbot_provider: str | None = None
    has_live_chat: bool = False
    has_phone: bool = False
    has_email: bool = False
    has_address: bool = False
    has_clear_cta: bool = False
    cta_evidence: list[str] = field(default_factory=list)
    technology_detected: list[str] = field(default_factory=list)
    has_whatsapp: bool = False
    social_links: list[str] = field(default_factory=list)
    responsive_css_hint: bool = False


def analyze_pages(crawl: CrawlResult) -> PageSignals:
    merged = PageSignals()
    for page in crawl.pages:
        sig = analyze_html(page)
        _merge(merged, sig)
    return merged


def analyze_html(page: FetchedPage) -> PageSignals:
    soup = BeautifulSoup(page.html or "", "lxml")
    text = soup.get_text(" ", strip=True)
    html_lower = (page.html or "").lower()
    signals = PageSignals()

    title = soup.find("title")
    if title and title.get_text(strip=True):
        signals.has_title = True
        signals.title_text = title.get_text(strip=True)[:200]

    meta_desc = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    if meta_desc and (meta_desc.get("content") or "").strip():
        signals.has_meta_description = True

    if soup.find("h1"):
        signals.has_h1 = True

    if soup.find("link", rel=lambda v: v and "icon" in " ".join(v).lower() if isinstance(v, list) else "icon" in str(v).lower()):
        signals.has_favicon = True

    canonical = soup.find("link", rel=lambda v: v and "canonical" in " ".join(v).lower() if isinstance(v, list) else "canonical" in str(v).lower())
    if canonical and canonical.get("href"):
        signals.has_canonical = True

    viewport = soup.find("meta", attrs={"name": re.compile("^viewport$", re.I)})
    if viewport and (viewport.get("content") or "").strip():
        signals.has_viewport = True

    images = soup.find_all("img")
    signals.image_count = len(images)
    signals.images_with_alt = sum(1 for img in images if (img.get("alt") or "").strip())

    host = (urlparse(page.final_url).hostname or "").lower()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        abs_host = urlparse(href).hostname
        if abs_host and abs_host.lower().lstrip("www.") != host.lstrip("www."):
            signals.external_link_count += 1
        else:
            signals.internal_link_count += 1

    signals.has_contact_form = _detect_contact_form(soup)
    booking, evidence = _detect_booking(soup, page.final_url)
    signals.has_booking = booking
    signals.booking_evidence = evidence

    provider = _detect_chatbot(html_lower)
    if provider:
        signals.has_chatbot = True
        signals.chatbot_provider = provider
        signals.has_live_chat = True

    signals.has_phone = bool(PHONE_RE.search(text)) or bool(soup.find("a", href=re.compile(r"^tel:", re.I)))
    signals.has_email = bool(EMAIL_RE.search(text)) or bool(soup.find("a", href=re.compile(r"^mailto:", re.I)))
    signals.has_address = _detect_address(soup, text)

    cta, cta_ev = _detect_cta(soup)
    signals.has_clear_cta = cta
    signals.cta_evidence = cta_ev

    signals.technology_detected = _detect_tech(html_lower)
    signals.has_whatsapp = "wa.me" in html_lower or "api.whatsapp.com" in html_lower
    signals.social_links = _social_links(soup)
    signals.responsive_css_hint = any(
        hint in html_lower
        for hint in ("@media", "max-width", "min-width", "bootstrap", "tailwind")
    )
    return signals


def _merge(target: PageSignals, src: PageSignals) -> None:
    for field_name in (
        "has_title",
        "has_meta_description",
        "has_h1",
        "has_favicon",
        "has_canonical",
        "has_viewport",
        "has_contact_form",
        "has_booking",
        "has_chatbot",
        "has_live_chat",
        "has_phone",
        "has_email",
        "has_address",
        "has_clear_cta",
        "has_whatsapp",
        "responsive_css_hint",
    ):
        if getattr(src, field_name):
            setattr(target, field_name, True)
    if src.title_text and not target.title_text:
        target.title_text = src.title_text
    if src.chatbot_provider and not target.chatbot_provider:
        target.chatbot_provider = src.chatbot_provider
    target.image_count += src.image_count
    target.images_with_alt += src.images_with_alt
    target.internal_link_count += src.internal_link_count
    target.external_link_count += src.external_link_count
    for item in src.booking_evidence:
        if item not in target.booking_evidence:
            target.booking_evidence.append(item)
    for item in src.cta_evidence:
        if item not in target.cta_evidence:
            target.cta_evidence.append(item)
    for tech in src.technology_detected:
        if tech not in target.technology_detected:
            target.technology_detected.append(tech)
    for link in src.social_links:
        if link not in target.social_links:
            target.social_links.append(link)


def _detect_contact_form(soup: BeautifulSoup) -> bool:
    for form in soup.find_all("form"):
        inputs = form.find_all(["input", "textarea"])
        names = " ".join(
            f'{(i.get("name") or "")} {(i.get("type") or "")} {(i.get("placeholder") or "")} {(i.get("id") or "")}'
            for i in inputs
        ).lower()
        if any(k in names for k in ("email", "message", "contact", "name", "phone")):
            if form.find(["textarea", "input"]):
                return True
    return False


def _detect_booking(soup: BeautifulSoup, base_url: str) -> tuple[bool, list[str]]:
    evidence: list[str] = []
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        label = a.get_text(" ", strip=True).lower()
        href_l = href.lower()
        if any(p in href_l for p in BOOKING_PROVIDERS):
            evidence.append(href)
            continue
        # Require booking intent in href path OR strong CTA label + booking href hint
        path = urlparse(href).path.lower() if "://" in href or href.startswith("/") else href_l
        href_hint = any(h in path for h in BOOKING_HREF_HINTS)
        label_hint = any(h in label for h in ("book", "appointment", "schedule", "reserve"))
        if href_hint and (label_hint or any(h in path for h in ("/book", "booking", "appointment", "schedule", "calendly"))):
            evidence.append(href if href.startswith("http") else f"{base_url.rstrip('/')}/{href.lstrip('/')}")
    # iframe embeds
    for iframe in soup.find_all("iframe", src=True):
        src = iframe["src"].lower()
        if any(p in src for p in BOOKING_PROVIDERS):
            evidence.append(iframe["src"])
    # de-dupe
    uniq: list[str] = []
    for e in evidence:
        if e not in uniq:
            uniq.append(e)
    return (len(uniq) > 0, uniq[:10])


def _detect_chatbot(html_lower: str) -> str | None:
    for provider, needles in CHATBOT_SIGNATURES.items():
        if any(n.lower() in html_lower for n in needles):
            return provider
    return None


def _detect_tech(html_lower: str) -> list[str]:
    found: list[str] = []
    for name, needles in TECH_SIGNATURES.items():
        if any(n.lower() in html_lower for n in needles):
            found.append(name)
    return found


def _detect_address(soup: BeautifulSoup, text: str) -> bool:
    if soup.find(attrs={"itemtype": re.compile("PostalAddress", re.I)}):
        return True
    if soup.find("address") and len(soup.find("address").get_text(strip=True)) > 10:
        return True
    # Conservative postal pattern (US-ish)
    if re.search(r"\b\d{1,5}\s+[A-Za-z0-9.\s]{3,40}\b(?:Ave|St|Rd|Blvd|Dr|Lane|Ln|Way)\b", text, re.I):
        return True
    return False


def _detect_cta(soup: BeautifulSoup) -> tuple[bool, list[str]]:
    evidence: list[str] = []
    candidates = soup.find_all(["a", "button"])
    for el in candidates:
        label = el.get_text(" ", strip=True).lower()
        if not label or len(label) > 60:
            continue
        for phrase in CTA_PHRASES:
            if phrase in label:
                evidence.append(el.get_text(" ", strip=True)[:80])
                break
    uniq: list[str] = []
    for e in evidence:
        if e not in uniq:
            uniq.append(e)
    return (len(uniq) > 0, uniq[:10])


def _social_links(soup: BeautifulSoup) -> list[str]:
    hosts = ("facebook.com", "instagram.com", "linkedin.com", "twitter.com", "x.com", "youtube.com")
    found: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        low = href.lower()
        if any(h in low for h in hosts):
            found.append(href)
    return found[:10]
