# MVP FastAPI backend — Phase 2

## Setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Repo-root `.env` must contain `DATABASE_URL`.

## Run

From the `backend` directory:

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

API docs: http://127.0.0.1:8001/docs

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/api/conferences` | List conferences |
| POST | `/api/conferences` | Create conference |
| GET | `/api/conferences/{id}` | Detail + organizers + evidence |
| PATCH | `/api/conferences/{id}` | Update conference |
| POST | `/api/conferences/{id}/organizers` | Add organizer + evidence |
| GET | `/api/organizers` | List organizers |
| POST | `/api/organizers` | Create organizer + evidence |
| PATCH | `/api/organizers/{id}` | Update organizer |
| GET | `/api/export/leads.xlsx` | Download leads Excel |
| POST | `/api/search-runs` | Create run; set `execute_search: false` for queries only |
| GET | `/api/search-runs` | List runs |
| GET | `/api/search-runs/{id}` | Run detail + queries + hits + crawl data |
| POST | `/api/search-runs/{id}/crawl` | Score, select sites, crawl, persist pages + evidence |

Organizer create requires nested `evidence` with `source_url` and `extracted_text_snippet`.

## Smoke tests

```powershell
python ../scripts/smoke_test_api.py
python ../scripts/smoke_test_search_runs.py
python ../scripts/smoke_test_crawl.py
```
