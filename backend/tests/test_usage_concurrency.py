"""Phase 13 — concurrency-safe usage increments."""

from __future__ import annotations

import threading

from app.services.billing.usage import UsageLimitError, get_or_create_usage_period, get_usage_value, increment_usage


def test_concurrent_increments_respect_limit(db_engine, SessionLocal, auth_tenant):
    org_id = auth_tenant["organization_id"]
    # Seed period on main connection
    session = SessionLocal()
    get_or_create_usage_period(session, org_id)
    for _ in range(24):
        increment_usage(session, org_id, "ai_qualifications", amount=1)
    session.close()

    successes = []
    errors = []
    lock = threading.Lock()

    def worker():
        s = SessionLocal()
        try:
            increment_usage(s, org_id, "ai_qualifications", amount=1)
            with lock:
                successes.append(1)
        except UsageLimitError:
            with lock:
                errors.append(1)
        finally:
            s.close()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(successes) == 1
    assert len(errors) == 1

    verify = SessionLocal()
    assert get_usage_value(verify, org_id, "ai_qualifications") == 25
    verify.close()
