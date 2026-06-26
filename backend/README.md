# MVP FastAPI backend

FastAPI service for the Conference Organizer Lead Finder. Runs the PoC pipeline via `poc_bridge`, persists to Supabase, and exposes CRUD + export.

**Version:** 0.7.0

## Setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
```

Repo-root `.env` must contain `DATABASE_URL`.

## Run

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

- Docs: http://127.0.0.1:8001/docs  
- Health: http://127.0.0.1:8001/health  

Default port is **8001** (8000 often in use locally).

## Architecture

```text
backend/app/
  main.py                 FastAPI app + CORS for Streamlit
  api/                    REST routers
  models.py               SQLAlchemy models
  schemas/                Pydantic request/response
  services/
    poc_bridge.py         Imports poc/backend pipeline modules
    search_run.py         Search-only runs
    crawl_run.py          Crawl + block-list logic
    extract_run.py        Email extract + organizer persist
    pipeline_run.py       Full execute chain
    exporter.py           Excel export from DB
```

Pipeline logic lives in `poc/backend/` and is loaded at runtime — no duplicate copy yet.

## API endpoints

### Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |

### Conferences

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/conferences` | List (filters: `field`, `region`, `status`, `has_email`) |
| POST | `/api/conferences` | Create |
| GET | `/api/conferences/{id}` | Detail + organizers + evidence + crawled pages |
| PATCH | `/api/conferences/{id}` | Update |
| POST | `/api/conferences/{id}/retry-crawl` | Clear `crawl_blocked` for re-crawl |
| GET | `/api/conferences/{id}/organizers` | List organizers |
| POST | `/api/conferences/{id}/organizers` | Add organizer + evidence |
| GET | `/api/conferences/{id}/evidence` | List evidence |

### Organizers

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/organizers` | List (`conference_id` filter) |
| POST | `/api/organizers` | Create + evidence |
| PATCH | `/api/organizers/{id}` | Update |
| POST | `/api/organizers/{id}/evidence` | Add evidence |

### Search runs

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/search-runs` | Create run; flags: `execute_search`, `execute_crawl`, `execute_extract` |
| GET | `/api/search-runs` | List runs |
| GET | `/api/search-runs/{id}` | Detail + queries + hits + crawl data |
| POST | `/api/search-runs/{id}/crawl` | Crawl selected sites |
| POST | `/api/search-runs/{id}/extract` | Extract emails from crawled pages |
| POST | `/api/search-runs/{id}/execute` | Search (if needed) + crawl + extract |

### Export

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/export/leads.xlsx` | Primary leads Excel |

Organizer create (manual) requires nested `evidence` with `source_url` and `extracted_text_snippet`.

## Conference statuses

`discovered`, `official_site_found`, `crawled`, `extracted`, `crawl_blocked`, `needs_review`, `verified`, `rejected`

`crawl_blocked` — auto-crawl failed (403, empty, etc.); skipped on future runs until `retry-crawl`.

## Smoke tests

From repo root, with API running:

```powershell
python scripts/smoke_test_api.py
python scripts/smoke_test_search_runs.py
python scripts/smoke_test_crawl.py
python scripts/smoke_test_execute.py
python scripts/smoke_test_review.py
```
