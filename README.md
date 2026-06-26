# Conference Organizer Lead Finder

Find conference **organizer leads** by field and region, with evidence-backed export for Confiva sales outreach.

| Layer | What | Folder |
|-------|------|--------|
| **MVP (use this)** | API + Supabase + review UI | `backend/`, `frontend/` |
| **PoC (standalone)** | Local Streamlit, no database | `poc/` |

Docs: [MVP roadmap](docs/mvp_roadmap.md) · [PoC spec](docs/poc_v1_spec.md)

---

## Prerequisites

- **Python 3.11+** (3.12 recommended for Playwright)
- **Supabase** project with migrations applied
- Repo-root **`.env`** with your database connection string

---

## One-time setup

### 1. Environment

Create `.env` in the repo root:

```env
DATABASE_URL=postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
```

Optional:

```env
API_HOST=127.0.0.1
API_PORT=8001
```

Phase 8 (LLM extraction):

```env
PERPLEXITY_API_KEY=pplx-...
EXTRACTION_USE_LLM=true
# PERPLEXITY_MODEL=sonar
```

The review UI can also use `API_BASE_URL` (defaults to `http://127.0.0.1:8001`).

### 2. Database migrations

```powershell
python scripts/apply_migrations.py
python scripts/verify_schema.py
```

### 3. Backend dependencies

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
```

### 4. Review UI dependencies

```powershell
cd frontend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

---

## Run the MVP (daily use)

You need **two terminals** — API + one UI for everything (search, review, export).

### Terminal 1 — API

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

- API docs: http://127.0.0.1:8001/docs
- Health: http://127.0.0.1:8001/health

### Terminal 2 — App (search + review + export)

```powershell
cd frontend
.\.venv\Scripts\Activate.ps1
streamlit run app.py
```

- App: http://localhost:8501
- **Find leads** — run a new search pipeline
- **Review leads** — edit contacts, verify/reject, view evidence
- **Export** — download Excel from the sidebar

---

## Run a new search

### Option A — API docs (interactive)

1. Open http://127.0.0.1:8001/docs
2. `POST /api/search-runs` — create a run (example body below)
3. `POST /api/search-runs/{id}/execute` — full pipeline (search + crawl + extract)

Or create and run everything in one request:

```json
{
  "field": "Healthcare",
  "region": "Slovenia",
  "selected_months": ["2026-06", "2026-07"],
  "max_conferences": 5,
  "manual_official_url": "",
  "execute_search": true,
  "execute_crawl": true,
  "execute_extract": true
}
```

### Option B — Smoke test script

```powershell
python scripts/smoke_test_execute.py
```

Takes a few minutes (live search + crawl). Results appear in the review UI and export.

### Option C — Step by step

```text
POST /api/search-runs          → search only (execute_search: true)
POST /api/search-runs/{id}/crawl
POST /api/search-runs/{id}/extract
```

Or `POST /api/search-runs/{id}/execute` for crawl + extract on an existing run.

---

## PoC only (no Supabase)

Standalone local pipeline — useful for quick experiments without the database.

```powershell
cd poc
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
streamlit run frontend/app.py
```

See [poc/README.md](poc/README.md) for PoC details.

---

## Smoke tests

With the API running on port 8001:

```powershell
python scripts/test_supabase_connection.py
python scripts/smoke_test_api.py
python scripts/smoke_test_search_runs.py
python scripts/smoke_test_crawl.py
python scripts/smoke_test_execute.py
python scripts/smoke_test_review.py
```

---

## Project layout

```text
backend/          FastAPI + SQLAlchemy (MVP API)
frontend/         Streamlit review UI (MVP)
poc/              Original PoC pipeline + Streamlit
supabase/         SQL migrations
scripts/          Migrations, smoke tests, utilities
docs/             Specs and roadmap
.env              Secrets (gitignored) — DATABASE_URL required
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Port 8001 in use | Stop the other process or set `API_PORT` in `.env` |
| `DATABASE_URL` / 401 errors | Check Supabase password and connection string in `.env` |
| Empty review list | Run a pipeline first (`smoke_test_execute.py` or `/execute`) |
| Crawl returns 0 pages | Try `manual_official_url` with a known conference site |
| Review UI can't reach API | Ensure API is running; set `$env:API_BASE_URL = "http://127.0.0.1:8001"` |

---

## What's next

MVP Phases 1–6 are complete. Phase 7 (Supabase Auth + RLS) is for multi-user or hosted deploy. See [docs/mvp_roadmap.md](docs/mvp_roadmap.md).
