"""URL normalization and SSRF-safe validation for website crawling."""

from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urljoin, urlparse, urlunparse


PRIVATE_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


class UnsafeURLError(Exception):
    pass


def normalize_website_url(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = raw.strip()
    if not value:
        return None
    if not re.match(r"^https?://", value, flags=re.IGNORECASE):
        value = f"https://{value}"
    parsed = urlparse(value)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise UnsafeURLError("Only http and https URLs are allowed")
    if not parsed.netloc:
        raise UnsafeURLError("URL host is required")
    # Drop fragments; keep path/query
    cleaned = parsed._replace(fragment="")
    return urlunparse(cleaned)


def is_private_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(addr in net for net in PRIVATE_NETWORKS)


def assert_public_url(url: str, *, resolve_dns: bool = True) -> None:
    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        raise UnsafeURLError("URL host is required")
    lowered = host.lower()
    if lowered in {"localhost", "metadata.google.internal", "metadata"} or lowered.endswith(".local"):
        raise UnsafeURLError("Local/internal hosts are not allowed")
    if lowered.endswith(".internal") or lowered in {"169.254.169.254", "[::1]"}:
        raise UnsafeURLError("Metadata/internal hosts are not allowed")

    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        addr = None
    if addr is not None:
        if any(addr in net for net in PRIVATE_NETWORKS):
            raise UnsafeURLError("Private IP targets are not allowed")
        return

    if not resolve_dns:
        return

    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise UnsafeURLError(f"Unable to resolve host: {host}") from exc

    for info in infos:
        ip = info[4][0]
        if is_private_ip(ip):
            raise UnsafeURLError("Host resolves to a private/internal address")


def same_registrable_host(url_a: str, url_b: str) -> bool:
    a = urlparse(url_a).hostname or ""
    b = urlparse(url_b).hostname or ""
    return a.lower().lstrip("www.") == b.lower().lstrip("www.")


def absolutize(base: str, href: str) -> str | None:
    if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
        return None
    try:
        return urljoin(base, href)
    except Exception:
        return None
