"""Local MX / role / free-provider signals — never prove mailbox existence alone."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

ROLE_LOCALS = {
    "info",
    "sales",
    "support",
    "hello",
    "contact",
    "booking",
    "bookings",
    "office",
    "admin",
    "help",
    "marketing",
    "enquiries",
    "inquiry",
    "inquiries",
    "appointments",
    "appointment",
}

FREE_PROVIDERS = {
    "gmail.com",
    "googlemail.com",
    "outlook.com",
    "hotmail.com",
    "live.com",
    "yahoo.com",
    "ymail.com",
    "icloud.com",
    "aol.com",
    "proton.me",
    "protonmail.com",
}


def email_domain(email: str) -> str | None:
    if "@" not in email:
        return None
    return email.rsplit("@", 1)[-1].lower().strip() or None


def is_role_based_email(email: str) -> bool:
    local = email.split("@", 1)[0].lower().replace(".", "").replace("-", "").replace("_", "")
    raw_local = email.split("@", 1)[0].lower()
    return raw_local in ROLE_LOCALS or local in ROLE_LOCALS


def is_free_email_provider(email: str) -> bool:
    domain = email_domain(email)
    return bool(domain and domain in FREE_PROVIDERS)


def check_mx(domain: str | None) -> bool | None:
    """Return True/False if MX can be determined, else None."""
    if not domain:
        return None
    try:
        import dns.resolver

        answers = dns.resolver.resolve(domain, "MX")
        return len(list(answers)) > 0
    except Exception as exc:  # noqa: BLE001 — treat any DNS failure as unknown/unavailable
        # NXDOMAIN / NoAnswer → False; timeout/config → None
        name = type(exc).__name__
        if name in {"NXDOMAIN", "NoAnswer", "NoNameservers"}:
            return False
        logger.info("MX lookup inconclusive domain=%s err=%s", domain, name)
        return None
