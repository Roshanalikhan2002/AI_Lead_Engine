"""Email sending provider abstraction — never claims delivery without provider events."""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from app.core.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class SendResult:
    status: str  # sent | simulated | failed | blocked
    provider_message_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    retryable: bool = False
    provider_name: str = "none"
    test_mode: bool = True


@dataclass
class DeliveryStatusResult:
    status: str  # sent | delivered | bounced | failed | unknown
    provider_message_id: str
    raw_event: str | None = None


class EmailSendingProvider(Protocol):
    name: str

    def send_email(
        self,
        *,
        sender_email: str,
        sender_name: str,
        recipient_email: str,
        subject: str,
        body: str,
        idempotency_key: str,
    ) -> SendResult: ...

    def get_delivery_status(self, provider_message_id: str) -> DeliveryStatusResult: ...


class UnconfiguredEmailProvider:
    name = "none"

    def send_email(self, **kwargs) -> SendResult:
        return SendResult(
            status="failed",
            error_code="provider_unconfigured",
            error_message="Email sending provider not configured",
            retryable=False,
            provider_name=self.name,
            test_mode=True,
        )

    def get_delivery_status(self, provider_message_id: str) -> DeliveryStatusResult:
        return DeliveryStatusResult(status="unknown", provider_message_id=provider_message_id)


class MockEmailProvider:
    """Deterministic offline/test provider — NEVER a real delivery."""

    name = "mock"

    def send_email(
        self,
        *,
        sender_email: str,
        sender_name: str,
        recipient_email: str,
        subject: str,
        body: str,
        idempotency_key: str,
    ) -> SendResult:
        if "fail-case" in recipient_email.lower() or "fail-case" in subject.lower():
            return SendResult(
                status="failed",
                error_code="mock_failure",
                error_message="Mock provider simulated failure",
                retryable=True,
                provider_name=self.name,
                test_mode=True,
            )
        if "auth-fail" in recipient_email.lower():
            return SendResult(
                status="failed",
                error_code="authentication_failure",
                error_message="Mock authentication failure",
                retryable=False,
                provider_name=self.name,
                test_mode=True,
            )
        msg_id = f"mock_{uuid.uuid4().hex[:16]}"
        return SendResult(
            status="simulated",
            provider_message_id=msg_id,
            provider_name=self.name,
            test_mode=True,
        )

    def get_delivery_status(self, provider_message_id: str) -> DeliveryStatusResult:
        return DeliveryStatusResult(status="sent", provider_message_id=provider_message_id, raw_event="mock")


class HttpEmailProvider:
    """
    Generic HTTP JSON sending provider.
    POST {api_url} with JSON payload and Authorization bearer / X-Api-Key.
    Expected response: {"id": "...", "status": "accepted"|"sent"|"failed", ...}
    """

    name = "http"

    def __init__(
        self,
        *,
        api_url: str,
        api_key: str,
        timeout: float = 20.0,
        max_retries: int = 2,
        client=None,
    ):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max(0, min(5, max_retries))
        self._client = client

    def send_email(
        self,
        *,
        sender_email: str,
        sender_name: str,
        recipient_email: str,
        subject: str,
        body: str,
        idempotency_key: str,
    ) -> SendResult:
        import httpx

        client = self._client or httpx
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "X-Api-Key": self.api_key,
            "Idempotency-Key": idempotency_key,
        }
        payload = {
            "from": {"email": sender_email, "name": sender_name},
            "to": [{"email": recipient_email}],
            "subject": subject,
            "text": body,
            "html": None,
        }
        delay = 0.5
        last = SendResult(
            status="failed",
            error_code="provider_unavailable",
            error_message="Email provider unavailable",
            retryable=True,
            provider_name=self.name,
            test_mode=False,
        )
        for attempt in range(self.max_retries + 1):
            try:
                response = client.post(self.api_url, json=payload, headers=headers, timeout=self.timeout)
                if response.status_code == 429:
                    last = SendResult(
                        status="failed",
                        error_code="rate_limited",
                        error_message="Provider rate limited",
                        retryable=True,
                        provider_name=self.name,
                        test_mode=False,
                    )
                elif response.status_code >= 500:
                    last = SendResult(
                        status="failed",
                        error_code="provider_error",
                        error_message="Provider temporary error",
                        retryable=True,
                        provider_name=self.name,
                        test_mode=False,
                    )
                elif response.status_code >= 400:
                    return SendResult(
                        status="failed",
                        error_code="provider_rejected",
                        error_message="Provider rejected request",
                        retryable=False,
                        provider_name=self.name,
                        test_mode=False,
                    )
                else:
                    data: dict[str, Any] = {}
                    try:
                        data = response.json() if hasattr(response, "json") else {}
                    except Exception:
                        data = {}
                    msg_id = str(data.get("id") or data.get("message_id") or uuid.uuid4())
                    # Acceptance ≠ delivery
                    return SendResult(
                        status="sent",
                        provider_message_id=msg_id,
                        provider_name=self.name,
                        test_mode=False,
                    )
            except Exception as exc:  # noqa: BLE001
                msg = str(exc).lower()
                logger.warning("HTTP email send attempt %s failed: %s", attempt + 1, type(exc).__name__)
                retryable = "timeout" in msg or "connection" in msg
                last = SendResult(
                    status="failed",
                    error_code="timeout" if "timeout" in msg else "provider_unavailable",
                    error_message="Email provider timeout" if "timeout" in msg else "Email provider unavailable",
                    retryable=retryable,
                    provider_name=self.name,
                    test_mode=False,
                )
            if attempt >= self.max_retries or not last.retryable:
                break
            time.sleep(delay)
            delay = min(8.0, delay * 2)
        return last

    def get_delivery_status(self, provider_message_id: str) -> DeliveryStatusResult:
        return DeliveryStatusResult(status="unknown", provider_message_id=provider_message_id)


def get_email_sending_provider(settings: Settings) -> EmailSendingProvider:
    # Test mode always uses mock — never real send
    if settings.email_test_mode or not settings.email_send_enabled:
        if settings.email_test_mode:
            return MockEmailProvider()
        name = (settings.email_sending_provider or "").strip().lower()
        if name == "mock":
            return MockEmailProvider()
        return UnconfiguredEmailProvider()

    name = (settings.email_sending_provider or "").strip().lower()
    if not name or name in {"none", "off"}:
        return UnconfiguredEmailProvider()
    if name == "mock":
        return MockEmailProvider()
    if name in {"http", "api", "custom", "resend", "sendgrid", "postmark", "mailgun", "ses"}:
        key = (settings.email_sending_api_key or "").strip()
        url = (settings.email_sending_api_url or "").strip()
        if not key or not url:
            return UnconfiguredEmailProvider()
        return HttpEmailProvider(
            api_url=url,
            api_key=key,
            timeout=settings.email_send_timeout_seconds,
            max_retries=settings.email_send_max_retries,
        )
    return UnconfiguredEmailProvider()
