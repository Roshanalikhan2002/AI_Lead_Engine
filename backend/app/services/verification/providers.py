"""Email verification provider abstraction — never invents deliverability."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class ProviderResult:
    status: str  # pending|valid|invalid|risky|unknown|blocked|error
    is_valid: bool | None = None
    is_risky: bool | None = None
    is_disposable: bool | None = None
    is_role_based: bool | None = None
    is_free_provider: bool | None = None
    mx_found: bool | None = None
    summary: str | None = None
    provider_name: str = "none"


class EmailVerificationProvider(Protocol):
    name: str

    def verify_email(self, email: str) -> ProviderResult: ...


class UnconfiguredProvider:
    """Default when no provider/API key is configured — never claims valid."""

    name = "none"

    def verify_email(self, email: str) -> ProviderResult:
        return ProviderResult(
            status="unknown",
            is_valid=None,
            is_risky=None,
            is_disposable=None,
            summary="No verification provider configured",
            provider_name=self.name,
        )


class MockVerificationProvider:
    """
    Offline/QA-only deterministic provider.
    NOT a real deliverability check — used for tests and local mock mode.
    """

    name = "mock"

    def verify_email(self, email: str) -> ProviderResult:
        local, _, domain = email.partition("@")
        domain = domain.lower()
        local = local.lower()

        if local.startswith("invalid") or local == "bounce":
            return ProviderResult(
                status="invalid",
                is_valid=False,
                is_risky=False,
                is_disposable=False,
                summary="Mock: invalid pattern",
                provider_name=self.name,
            )
        if domain in {"mailinator.com", "tempmail.com", "10minutemail.com"} or local.startswith("temp"):
            return ProviderResult(
                status="risky",
                is_valid=None,
                is_risky=True,
                is_disposable=True,
                summary="Mock: disposable pattern",
                provider_name=self.name,
            )
        if local.startswith("unknown") or domain.endswith(".unknown"):
            return ProviderResult(
                status="unknown",
                is_valid=None,
                summary="Mock: uncertain pattern",
                provider_name=self.name,
            )
        if local.startswith("error"):
            return ProviderResult(
                status="error",
                summary="Mock: provider error pattern",
                provider_name=self.name,
            )
        # Default mock "valid" for otherwise normal addresses — QA only
        return ProviderResult(
            status="valid",
            is_valid=True,
            is_risky=False,
            is_disposable=False,
            summary="Mock: accepted pattern",
            provider_name=self.name,
        )


class HttpJsonVerificationProvider:
    """
    Generic HTTP JSON provider.
    Expects POST {api_url} with JSON {"email": "..."} and header Authorization: Bearer <key>
    or X-Api-Key, and response fields compatible with our normalizer.
    """

    name = "http"

    def __init__(self, *, api_url: str, api_key: str, timeout: float = 15.0, client=None):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._client = client

    def verify_email(self, email: str) -> ProviderResult:
        import httpx

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "X-Api-Key": self.api_key,
        }
        try:
            if self._client is not None:
                response = self._client.post(self.api_url, json={"email": email}, headers=headers)
            else:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(self.api_url, json={"email": email}, headers=headers)
        except httpx.TimeoutException:
            return ProviderResult(status="error", summary="Provider timeout", provider_name=self.name)
        except httpx.HTTPError:
            return ProviderResult(status="error", summary="Provider unavailable", provider_name=self.name)

        if response.status_code == 429:
            return ProviderResult(status="error", summary="Provider rate limited", provider_name=self.name)
        if response.status_code in {401, 403}:
            return ProviderResult(status="error", summary="Provider authentication failed", provider_name=self.name)
        if response.status_code >= 400:
            return ProviderResult(status="error", summary=f"Provider HTTP {response.status_code}", provider_name=self.name)

        try:
            payload = response.json()
        except ValueError:
            return ProviderResult(status="error", summary="Malformed provider response", provider_name=self.name)

        if not isinstance(payload, dict):
            return ProviderResult(status="error", summary="Malformed provider response", provider_name=self.name)

        return normalize_provider_payload(payload, provider_name=self.name)


def normalize_provider_payload(payload: dict, *, provider_name: str) -> ProviderResult:
    """Map common provider JSON shapes into our internal format."""
    status = str(payload.get("status") or payload.get("result") or payload.get("deliverability") or "unknown").lower()
    status_map = {
        "deliverable": "valid",
        "valid": "valid",
        "ok": "valid",
        "undeliverable": "invalid",
        "invalid": "invalid",
        "risky": "risky",
        "accept_all": "risky",
        "unknown": "unknown",
        "error": "error",
    }
    mapped = status_map.get(status, "unknown")

    is_disposable = _as_bool(payload.get("is_disposable") if "is_disposable" in payload else payload.get("disposable"))
    is_risky = _as_bool(payload.get("is_risky") if "is_risky" in payload else payload.get("risky"))
    if is_disposable is True and mapped == "valid":
        mapped = "risky"
        is_risky = True

    is_valid = _as_bool(payload.get("is_valid") if "is_valid" in payload else payload.get("valid"))
    if mapped == "valid":
        is_valid = True if is_valid is None else is_valid
    elif mapped == "invalid":
        is_valid = False if is_valid is None else is_valid

    return ProviderResult(
        status=mapped,
        is_valid=is_valid,
        is_risky=is_risky if is_risky is not None else (True if mapped == "risky" else False if mapped == "valid" else None),
        is_disposable=is_disposable,
        is_role_based=_as_bool(payload.get("is_role_based") if "is_role_based" in payload else payload.get("role")),
        is_free_provider=_as_bool(payload.get("is_free_provider") if "is_free_provider" in payload else payload.get("free")),
        mx_found=_as_bool(payload.get("mx_found") if "mx_found" in payload else payload.get("mx")),
        summary=str(payload.get("summary") or payload.get("message") or mapped)[:200],
        provider_name=provider_name,
    )


def _as_bool(value) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y"}:
            return True
        if lowered in {"false", "0", "no", "n"}:
            return False
    return None


def get_verification_provider(settings, *, client=None) -> EmailVerificationProvider:
    name = (settings.email_verification_provider or "").strip().lower()
    key = (settings.email_verification_api_key or "").strip()
    url = (settings.email_verification_api_url or "").strip()

    if not name or name in {"none", "off", "disabled"}:
        return UnconfiguredProvider()
    if name == "mock":
        return MockVerificationProvider()
    if name in {"http", "custom", "api"}:
        if not key or not url:
            return UnconfiguredProvider()
        return HttpJsonVerificationProvider(
            api_url=url,
            api_key=key,
            timeout=settings.verification_timeout_seconds,
            client=client,
        )
    # Unknown provider name without credentials → safe unknown
    if not key:
        return UnconfiguredProvider()
    if url:
        return HttpJsonVerificationProvider(
            api_url=url,
            api_key=key,
            timeout=settings.verification_timeout_seconds,
            client=client,
        )
    return UnconfiguredProvider()
