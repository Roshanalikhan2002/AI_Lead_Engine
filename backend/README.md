# LeadFlow AI — Backend (Phase 1)

## Setup

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # then edit values
```

## Configure

Set in `backend/.env`:

- `GOOGLE_PLACES_API_KEY` — Google Places API (New) key with Places API enabled
- `DATABASE_URL` — PostgreSQL URL, e.g. `postgresql+psycopg2://user:pass@localhost:5432/leadflow`
- `FRONTEND_URL` — `http://localhost:5173`
- `GOOGLE_PLACES_MOCK` — `false` in production. Set `true` **only** for offline QA (no live Google calls; leads stored with `source=google_places_mock`)

Create the database if needed, then start the API:

```bash
uvicorn app.main:app --reload --port 8000
```

Open docs: http://localhost:8000/docs

## Offline QA (no Google API key)

```bash
# backend/.env
GOOGLE_PLACES_MOCK=true
DATABASE_URL=sqlite:///./offline_qa.db
FRONTEND_URL=http://localhost:5173
```

Then run the API and frontend. Find Leads will discover fixture businesses only.
Do **not** enable `GOOGLE_PLACES_MOCK` in production.

## Tests

```bash
pytest -q
```

All Google Places HTTP is mocked in tests. No live Google requests are made.

## Phase 2 — Website analysis

Deterministic crawler + HTML signal extraction (no LLM).

Endpoints:

- `POST /api/websites/analyze/{lead_id}`
- `GET /api/websites/{lead_id}`
- `POST /api/websites/analyze-batch`
- `GET /api/websites/jobs/{job_id}`
- `POST /api/leads/{lead_id}/reanalyze-website`

Tests use local HTML fixtures only — no external network requests.

