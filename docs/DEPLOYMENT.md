# Production deployment, workers, backups

## Environments

| `APP_ENV` | Behavior |
|-----------|----------|
| `development` | Lenient; mocks allowed when explicitly set |
| `test` | Used by automated tests |
| `production` | Fails fast on weak `SECRET_KEY`, mock providers, inconsistent email flags |

Copy `backend/.env.example` → `backend/.env`. Never commit real credentials.

## Migrations

```bash
cd backend
alembic upgrade head
```

Do not edit historical migrations. Add a new revision when the schema changes.

## Background jobs / campaign scheduler

Local/dev may call:

```http
POST /api/campaigns/process-due
```

**Production must not rely on manual clicks.** Run a worker/cron that periodically invokes the same scheduler logic, e.g.:

```bash
# Example cron every minute (replace with your process manager)
curl -X POST https://api.example.com/api/campaigns/process-due
```

Or run a dedicated worker process that:

1. Claims due campaign recipients (existing locks)
2. Executes steps via the local `JobQueue` / `CampaignScheduler`
3. Retries transient failures with exponential backoff

`JOB_QUEUE_BACKEND=local` stores `job_records` in Postgres. Redis/Celery can replace `LocalJobQueue` later without rewriting product code.

## Health probes

- `GET /api/health` / `GET /api/health/live` — process up
- `GET /api/health/ready` — database reachable
- `GET /api/system/health` — providers + config (no secrets)
- `GET /api/system/providers` — safe provider modes

## Authentication boundary

JWT authentication with multi-tenant RBAC is implemented (Phase 12+).

See **[PRODUCTION_GO_LIVE.md](./PRODUCTION_GO_LIVE.md)** for the full go-live checklist, provider LIVE rules, workers, backups, and webhook notes.

Provider tests (`POST /api/system/providers/{name}/test`) require owner/admin (`integrations.manage`).

## Backups / recovery

**Requirement:** take regular PostgreSQL backups (e.g. `pg_dump` / managed snapshots).

Restore strategy:

1. Provision empty Postgres
2. Restore dump
3. Run `alembic upgrade head` only if the dump is from an older schema revision
4. Verify `/api/health/ready`

This project does not ship fake in-app backup buttons.

## Docker

- `backend/Dockerfile` — API image
- `Dockerfile.frontend` — static frontend build
- `docker-compose.yml` — **local development** Postgres + API only

Production should use your orchestrator (ECS, Kubernetes, etc.) with secrets via the platform — not files in the image.

## Observability hooks

Structured request logs include `request_id`, path, status, duration.

`AuditLog` tracks campaign/email/meeting/pipeline actions.

Wire your preferred error tracker / metrics by scraping logs or extending middleware — no paid vendor is required.
