"""Phase 14 — provider failure / degraded handling."""

from __future__ import annotations

from app.services.jobs.queue import backoff_seconds, is_retryable_error
from app.services.system.provider_tests import DEGRADED_FAILURE_THRESHOLD


def test_retry_only_transient():
    assert is_retryable_error("network timeout")
    assert is_retryable_error("429 rate limit")
    assert is_retryable_error("502 bad gateway")
    assert is_retryable_error("503 temporary")
    assert not is_retryable_error("invalid api key")
    assert not is_retryable_error("401 unauthorized")
    assert not is_retryable_error("403 forbidden")
    assert not is_retryable_error("suppressed recipient")


def test_backoff_increases():
    assert backoff_seconds(1) < backoff_seconds(3)


def test_degraded_threshold_defined():
    assert DEGRADED_FAILURE_THRESHOLD >= 3
