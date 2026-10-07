"""Provider-agnostic job queue — local now, Redis/Celery-ready later."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.job_record import JobRecord

logger = logging.getLogger(__name__)

RETRYABLE_MARKERS = (
    "timeout",
    "timed out",
    "429",
    "rate limit",
    "temporarily",
    "503",
    "502",
    "504",
    "connection reset",
    "connection refused",
)

NON_RETRYABLE_MARKERS = (
    "invalid api key",
    "unauthorized",
    "forbidden",
    "suppressed",
    "not configured",
    "validation",
    "invalid email",
    "permanent",
)


def is_retryable_error(message: str) -> bool:
    lower = (message or "").lower()
    if any(m in lower for m in NON_RETRYABLE_MARKERS):
        return False
    return any(m in lower for m in RETRYABLE_MARKERS)


def backoff_seconds(attempt: int) -> float:
    return min(300.0, (2 ** max(0, attempt - 1)) * 2.0)


class JobQueue(Protocol):
    def enqueue(
        self,
        job_type: str,
        payload: dict[str, Any] | None = None,
        *,
        idempotency_key: str | None = None,
        max_attempts: int | None = None,
    ) -> JobRecord: ...


class LocalJobQueue:
    """DB-backed job records + optional in-process execution (BackgroundTasks compatible)."""

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def enqueue(
        self,
        job_type: str,
        payload: dict[str, Any] | None = None,
        *,
        idempotency_key: str | None = None,
        max_attempts: int | None = None,
    ) -> JobRecord:
        if idempotency_key:
            q = self.db.query(JobRecord).filter(JobRecord.idempotency_key == idempotency_key)
            from app.core.tenant import get_current_tenant

            ctx = get_current_tenant()
            if ctx:
                q = q.filter(JobRecord.organization_id == ctx.organization_id)
            existing = q.one_or_none()
            if existing:
                return existing
        from app.core.tenant import get_current_tenant, require_org_id

        ctx = get_current_tenant()
        org_id = ctx.organization_id if ctx else None
        if org_id is None and payload and payload.get("organization_id"):
            org_id = uuid.UUID(str(payload["organization_id"]))
        if org_id is None:
            raise ValueError("organization_id required for jobs")
        row = JobRecord(
            organization_id=org_id,
            type=job_type,
            status="pending",
            attempts=0,
            max_attempts=max_attempts or self.settings.job_default_max_attempts,
            payload=payload or {},
            idempotency_key=idempotency_key,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def mark_running(self, job_id: uuid.UUID) -> JobRecord:
        row = self.db.get(JobRecord, job_id)
        if not row:
            raise ValueError("job_not_found")
        row.status = "running"
        row.attempts += 1
        row.started_at = datetime.now(timezone.utc)
        row.last_error = None
        self.db.commit()
        self.db.refresh(row)
        return row

    def mark_completed(self, job_id: uuid.UUID, result: dict | None = None) -> JobRecord:
        row = self.db.get(JobRecord, job_id)
        if not row:
            raise ValueError("job_not_found")
        row.status = "completed"
        row.result = result
        row.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(row)
        return row

    def mark_failed(self, job_id: uuid.UUID, error: str) -> JobRecord:
        row = self.db.get(JobRecord, job_id)
        if not row:
            raise ValueError("job_not_found")
        safe = (error or "unknown error")[:500]
        if is_retryable_error(safe) and row.attempts < row.max_attempts:
            row.status = "retrying"
            row.next_retry_at = datetime.now(timezone.utc) + timedelta(
                seconds=backoff_seconds(row.attempts)
            )
            row.last_error = safe
        else:
            row.status = "failed"
            row.last_error = safe
            row.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(row)
        return row

    def run(
        self,
        job_id: uuid.UUID,
        fn: Callable[[], dict | None],
    ) -> JobRecord:
        self.mark_running(job_id)
        started = time.perf_counter()
        try:
            result = fn() or {}
            row = self.mark_completed(job_id, result)
            logger.info(
                "job_completed id=%s type=%s duration_ms=%.0f",
                job_id,
                row.type,
                (time.perf_counter() - started) * 1000,
            )
            return row
        except Exception as exc:  # noqa: BLE001
            logger.exception("job_failed id=%s", job_id)
            return self.mark_failed(job_id, str(exc))


def get_job_queue(db: Session) -> LocalJobQueue:
    # Future: switch on JOB_QUEUE_BACKEND=redis
    return LocalJobQueue(db)
