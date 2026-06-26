# Conference Organizer Lead Finder

Find conference **organizer leads** by field and region, with evidence-backed export for Confiva sales outreach.

| Layer | What | Folder |
|-------|------|--------|
| **MVP (use this)** | API + Supabase + Streamlit app | `backend/`, `frontend/` |
| **PoC (standalone)** | Local pipeline, no database | `poc/` |

**Docs:** [MVP roadmap](docs/mvp_roadmap.md) · [PoC spec](docs/poc_v1_spec.md) · [Blueprint](docs/conference_organizer_contact_finder_blueprint.md)

**Status:** MVP Phases 1–6 complete (search → crawl → extract → review → export). Phase 7 (auth) not started.

---

## Prerequisites

- **Python 3.11+** (3.12 recommended for Playwright)
- **Supabase** project with migrations applied
- Repo-root **`.env`** with `DATABASE_URL`

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

The Streamlit app can use `API_BASE_URL` (defaults to `http://127.0.0.1:8001`).

### 2. Database migrations

```powershell
python scripts/apply_migrations.py
python scripts/verify_schema.py
```

### 3. Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
```

### 4. Frontend app

```powershell
cd frontend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Requires **Streamlit 1.36+** (sidebar navigation).

---

## Run (daily use)

Two terminals:

### Terminal 1 — API

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

- Docs: http://127.0.0.1:8001/docs  
- Health: http://127.0.0.1:8001/health  

### Terminal 2 — App

```powershell
cd frontend
.\.venv\Scripts\Activate.ps1
streamlit run app.py
```

Open http://localhost:8501

| Page | Purpose |
|------|---------|
| **Find leads** | Run full pipeline (search + crawl + extract) |
| **Review leads** | Filter, open, edit contacts, verify/reject |
| **Manual crawl** | Sites that blocked auto-crawl (403, etc.) |
| **Conference detail** | Opens from any list — breadcrumbs + back button |
| **Sidebar export** | Download `confiva_leads_*.xlsx` |

---

## Run a search

**Recommended:** use **Find leads** in the Streamlit app.

**API alternative** — `POST /api/search-runs` with:

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

Or on an existing run: `POST /api/search-runs/{id}/execute`

**Smoke test:**

```powershell
python scripts/smoke_test_execute.py
```

---

## What the pipeline does

1. **Search** — up to 30 localized queries (conference, congress, summit, symposium, convention, expo, event, fair + local terms)
2. **Filter & score** — drop news/spam; pick official sites
3. **Crawl** — fetch pages (HTTP + Playwright fallback)
4. **Extract** — regex/mailto emails, validate, rank
5. **Persist** — conferences, organizers, evidence in Supabase
6. **Block list** — sites that return 403 / empty are saved as `crawl_blocked` and skipped on future runs (see **Manual crawl**)

---

## PoC only (no Supabase)

```powershell
cd poc
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
streamlit run frontend/app.py
```

See [poc/README.md](poc/README.md). The MVP app in `frontend/` replaces this for normal use.

---

## Smoke tests

With API on port 8001:

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
backend/          FastAPI v0.7 — pipeline services + CRUD + export
frontend/         Streamlit app (search, review, manual crawl)
  pages/            Multipage UI
  lib/              Nav, sidebar, shared state
poc/              Original PoC (lifted via poc_bridge)
supabase/         SQL migrations
scripts/          apply_migrations, smoke tests
docs/             Specs and roadmap
.env              DATABASE_URL (gitignored)
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `.venv\Scripts\activate` fails on Windows | Use `.\.venv\Scripts\Activate.ps1` after `python -m venv .venv` |
| Port 8001 in use | Stop other process or set `API_PORT` in `.env` |
| `DATABASE_URL` / 401 | Check Supabase password in `.env` |
| Empty review list | Run **Find leads** or `smoke_test_execute.py` |
| Crawl 403 / 0 pages | Check **Manual crawl**; add contact manually; use **Retry auto-crawl** if site may work later |
| UI can't reach API | Start backend; `$env:API_BASE_URL = "http://127.0.0.1:8001"` |

---

## What's next

Phase 7 — Supabase Auth + RLS for multi-user or hosted deploy. See [docs/mvp_roadmap.md](docs/mvp_roadmap.md).
