# LeadFlow AI — Production Go-Live Runbook

This document covers production configuration, provider readiness, workers, backups, and incident handling.

**Never commit real secrets.** Copy `backend/.env.example` → `backend/.env`.

---

## Status vocabulary (do not blur)

| Status | Meaning |
|--------|---------|
| **IMPLEMENTED** | Code path exists in the product |
| **CONFIGURED** | Env/credentials present |
| **TEST** | Sandbox/mock/test-mode operation succeeded |
| **LIVE** | Real external success recorded; `mode=live` + `live_tested=true` |
| **LIVE-TESTED** | Same as LIVE evidence for that provider |
| **MOCK** | Explicit mock provider |
| **NOT CONFIGURED** | No credentials / provider unset |
| **NOT IMPLEMENTED** | Adapter not built (e.g. live Google/Outlook calendar) |
| **DISABLED** | Explicitly off (e.g. inbound) |
| **ERROR** | Probe failed / degraded |

**Configured ≠ Tested ≠ Live-tested ≠ Live-enabled.**

API key presence alone never implies LIVE.

---

## 1. Environments

| `APP_ENV` | Behavior |
|-----------|----------|
| `development` | Lenient; mocks allowed when explicitly set |
| `test` | Automated tests |
| `production` | Fail-fast on weak `SECRET_KEY`, mock providers, unsafe email flags |

Optional providers (calendar, billing) may remain **unavailable** without failing startup.

---

## 2. Database & migrations

```bash
cd backend
alembic upgrade head
```

Do not edit historical migrations. Latest provider-health revision: `0014_provider_health`.

### Backup / recovery (ops responsibility)

**Documented only — not auto-implemented by the app.**

- Take regular PostgreSQL backups (e.g. `pg_dump`, managed snapshots).
- Store backups encrypted off-host.
- Test restore on a staging database before go-live.
- Migration rollback: prefer forward-fix migrations; use `alembic downgrade -1` only with a tested restore plan.
- Retain audit / provider operation logs per your compliance policy.

---

## 3. Secrets & CORS

Required in production:

- `SECRET_KEY` — 32+ random characters
- `DATABASE_URL`
- `FRONTEND_URL` / `CORS_ORIGINS` — production domains (avoid relying on localhost defaults)

Terminate **HTTPS** at the reverse proxy / load balancer.

Never expose provider secrets to the frontend bundle or API responses.

---

## 4. Authentication

JWT access + refresh sessions with organization membership and RBAC are implemented.

- Protect the API with HTTPS
- Rotate `SECRET_KEY` carefully (invalidates sessions)
- Owner/admin only for provider tests, billing manage, and readiness endpoints

---

## 5. Provider configuration (Phase 15)

| Provider | Env | Default | LIVE / TEST rule |
|----------|-----|---------|------------------|
| Google Places | `GOOGLE_PLACES_API_KEY` / `GOOGLE_PLACES_MOCK` | unconfigured | LIVE only after successful Places probe (no leads created) |
| AI | `AI_PROVIDER`, `AI_API_KEY`, `AI_MODEL` | unconfigured | LIVE only after successful structured completion probe |
| Email verification | `EMAIL_VERIFICATION_PROVIDER`, keys | unconfigured | LIVE only after probe to `PROVIDER_TEST_EMAIL` |
| Email sending | `EMAIL_SEND_ENABLED=false`, `EMAIL_TEST_MODE=true` | safe defaults | LIVE send requires enabled + test mode false + `PROVIDER_TEST_EMAIL`; one test email only |
| Inbound replies | `REPLY_INBOUND_ENABLED=false` | disabled | LIVE after real webhook verify/parse/match |
| Calendar | `CALENDAR_PROVIDER` | unconfigured | Live Google/Outlook **NOT IMPLEMENTED**; mock create/cancel is MOCK |
| Billing | `BILLING_PROVIDER=unconfigured` | free plan OK | Stripe `sk_test_*` balance probe → **TEST** never LIVE |

### Isolation

- Isolated org slug: `provider-test` (Provider Test Organization)
- Lead source: `provider_test`
- Provider health / E2E operations do **not** increment customer usage counters
- Pipeline analytics exclude provider-test leads

### Provider test recipient

```
PROVIDER_TEST_EMAIL=you@your-domain.com
```

Required for email verification/sending live tests. Never use a discovered lead email automatically.

### Admin endpoints

```
GET  /api/system/providers
GET  /api/system/providers/matrix
POST /api/system/providers/{provider}/test
POST /api/system/providers/e2e-test?send_email=false
GET  /api/system/readiness
```

Requires `integrations.manage` (owner/admin). Rate limited (`PROVIDER_TEST_RATE_LIMIT_PER_MINUTE`).

### Offline vs external tests

- Default suite: `pytest` — deterministic; no external APIs required
- External probes: `tests/integration/providers/` — **skipped** unless credentials are present

```bash
pytest tests/integration/providers -m integration
```

---

## 6. Current provider matrix (honest)

Fill after real probes against your `backend/.env`. Values below reflect the **repository default** with **no secrets configured** (this environment had no `backend/.env`):

| Provider | Configured | Mode | Live Tested | Last Test | Result |
|----------|------------|------|-------------|-----------|--------|
| Google Places | NO | unavailable | NO | — | NOT CONFIGURED |
| AI (OpenAI) | NO | unavailable | NO | — | NOT CONFIGURED |
| Email Verification | NO | unavailable | NO | — | NOT CONFIGURED |
| Email Sending | YES (safe defaults) | test/disabled | NO | — | CONFIGURED / TEST defaults |
| Inbound Email | NO | disabled | NO | — | DISABLED |
| Calendar | NO | unavailable | NO | — | NOT CONFIGURED / NOT IMPLEMENTED (live) |
| Stripe Billing | NO | unavailable | NO | — | NOT CONFIGURED |

Update this table only after `POST /api/system/providers/{provider}/test` (or E2E) records verified success. Never invent PASS/LIVE.

---

## 7. Webhooks

| Webhook | Path | Notes |
|---------|------|-------|
| Email delivery | `POST /api/webhooks/email/{provider}` | Signature via `EMAIL_WEBHOOK_SECRET` |
| Billing | `POST /api/webhooks/billing/{provider}` | Signature + idempotency; never trust `organization_id` from body |

Public exceptions are explicit (booking, unsubscribe, webhooks, health, auth register/login).

Inbound email remains **DISABLED** until a real webhook is verified end-to-end.

---

## 8. Workers / cron

`JOB_QUEUE_BACKEND=local` (default) or `redis` (future).

Campaign due processing:

```http
POST /api/campaigns/process-due
```

**Phase 15:** do **not** activate bulk campaigns. Controlled provider tests only.

Retries use exponential backoff for transient provider errors; do not retry permanent failures (invalid key, suppressed recipient).

---

## 9. Health probes

- `GET /api/health/live` — process up
- `GET /api/health/ready` — database reachable
- `GET /api/system/health` — providers + auth (authenticated)
- `GET /api/system/config/validate` — structured config (admin)
- `GET /api/system/readiness` — go-live checklist (admin)
- `GET /api/system/providers/matrix` — provider matrix (admin)

---

## 10. Monitoring & rate limits

- External uptime on `/api/health/live` and `/api/health/ready`
- `API_RATE_LIMIT_*` settings
- Provider tests separately rate limited

---

## 11. Email & campaign safety

Before enabling real customer sending:

- Unsubscribe / suppression / bounce / complaint handling
- Rate limits + idempotency
- Approved draft required
- Never send if suppressed, draft unapproved, verification policy blocks, campaign paused, org disabled, or usage limit reached

Calendar: never AI auto-book. Flow remains meeting_request → user selects slot → provider confirms.

Billing: Stripe **TEST MODE only** for Phase 15 (`sk_test_*`). No custom card handling.

---

## 12. Rollback / incidents

1. Disable live email: `EMAIL_SEND_ENABLED=false`
2. Disable inbound: `REPLY_INBOUND_ENABLED=false`
3. Set `BILLING_PROVIDER=unconfigured` if Stripe issues (Free plan continues)
4. Redeploy previous image / git tag
5. Restore DB from backup if data corruption (ops)

Never mark a provider LIVE in status UIs after an incident until a new successful probe.

---

## 13. Anti-hallucination rule

Do **not** claim LIVE / CONNECTED / DELIVERED / BOOKED / PAID / VERIFIED unless the external provider returned a successful result supporting that claim. API key presence alone is not proof.
