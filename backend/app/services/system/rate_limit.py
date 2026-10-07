"""In-memory API rate limiter — configurable via settings."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from app.core.config import get_settings


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, *, limit: int, window_seconds: float = 60.0) -> bool:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > window_seconds:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True


_limiter = SlidingWindowLimiter()


def client_key(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host or "unknown"
    return "unknown"


def enforce_rate_limit(request: Request, *, sensitive: bool = False, public_booking: bool = False) -> None:
    settings = get_settings()
    if not settings.api_rate_limit_enabled:
        return
    if public_booking:
        limit = settings.public_booking_rate_limit_per_minute
        bucket = "booking"
    elif sensitive:
        limit = settings.api_rate_limit_sensitive_per_minute
        bucket = "sensitive"
    else:
        limit = settings.api_rate_limit_per_minute
        bucket = "default"
    key = f"{bucket}:{client_key(request)}"
    if not _limiter.allow(key, limit=limit):
        raise HTTPException(
            status_code=429,
            detail={"error": {"code": "RATE_LIMIT_EXCEEDED", "message": "Too many requests. Try again shortly."}},
        )


SENSITIVE_PREFIXES = (
    "/api/generate",
    "/api/leads/generate",
    "/api/websites",
    "/api/contacts",
    "/api/verification",
    "/api/outreach",
    "/api/campaigns",
    "/api/conversations",
    "/api/reply-suggestions",
    "/api/replies",
    "/api/meetings",
    "/api/meeting-slots",
    "/api/pipeline",
    "/api/system/providers",
)
