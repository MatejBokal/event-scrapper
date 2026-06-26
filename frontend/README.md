# Frontend — Confiva Lead Finder app

Streamlit multipage app: search, review, manual crawl, and export. Talks to the FastAPI backend only (no direct Supabase access).

## Setup

```powershell
cd frontend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Requires **Streamlit ≥ 1.36** (`st.navigation`, `st.Page`, `st.switch_page`).

## Run

**Start the API first** (see [backend/README.md](../backend/README.md)).

```powershell
streamlit run app.py
```

Open http://localhost:8501

Optional:

```powershell
$env:API_BASE_URL = "http://127.0.0.1:8001"
```

## Navigation

Sidebar sections:

| Section | Page | Description |
|---------|------|-------------|
| **Search** | Find leads | Field, region, months → full pipeline |
| **Leads** | Review leads | Filter list, open conference detail |
| **Leads** | Manual crawl | Blocked sites (403, etc.) for hand review |

**Conference detail** opens when you click Open (not listed in sidebar). Uses query param `?conference=<uuid>`, breadcrumbs, and **← Back**.

Bottom of sidebar: API status + **Export leads (.xlsx)**.

## Structure

```text
frontend/
  app.py              Entry point — run this
  api_client.py       HTTP client for FastAPI
  options.py          Field/region lists (sync with PoC)
  pages/
    find_leads.py
    review_leads.py
    manual_crawl.py
    conference_detail.py
  lib/
    nav.py            Breadcrumbs, open/back helpers
    sidebar.py        Global sidebar (API + export)
    constants.py
    state.py
```

## Manual crawl workflow

1. Site fails auto-crawl → saved as `crawl_blocked` in DB  
2. Appears on **Manual crawl** page  
3. **Open in browser ↗** → find organizer email manually  
4. **Open detail** → edit/add organizer in Review  
5. **Retry auto-crawl** — clears block for next pipeline run  

## Related

- [Root README](../README.md) — full setup  
- [Backend API](../backend/README.md) — endpoints  
