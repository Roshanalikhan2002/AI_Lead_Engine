import re
from urllib.parse import urlparse


def normalize_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    digits = re.sub(r"\D+", "", phone)
    return digits or None


def normalize_domain(website: str | None) -> str | None:
    if not website:
        return None
    value = website.strip()
    if not value:
        return None
    if not re.match(r"^https?://", value, flags=re.IGNORECASE):
        value = f"https://{value}"
    parsed = urlparse(value)
    host = (parsed.netloc or parsed.path).lower().strip()
    if host.startswith("www."):
        host = host[4:]
    host = host.split("/")[0].split("?")[0]
    return host or None


def normalize_company_key(name: str | None, address: str | None = None) -> str | None:
    if not name:
        return None
    base = re.sub(r"[^a-z0-9]+", "", name.lower())
    if address:
        base += "|" + re.sub(r"[^a-z0-9]+", "", address.lower())[:40]
    return base or None
