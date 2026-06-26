# Conference Contact Finder — PoC v1.1

Local proof-of-concept pipeline for **Confiva** ([confiva.com](https://confiva.com/)) sales lead generation.

Finds conference **organizer contacts** by field and region, with evidence-backed export.

> **For daily use, prefer the MVP app** in [`../frontend/`](../frontend/) (search + review + Supabase). This PoC folder is the pipeline source code, lifted by the API via `poc_bridge`.

See [docs/poc_v1_spec.md](../docs/poc_v1_spec.md) for the full specification.  
**MVP roadmap:** [docs/mvp_roadmap.md](../docs/mvp_roadmap.md)

## Structure

```text
poc/
  backend/          # Pipeline logic (search, crawl, extract, rank)
  frontend/         # Standalone Streamlit UI (legacy entry)
  requirements.txt
  README.md
```

## Setup

```powershell
cd poc
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
```

## Run (standalone, no database)

```powershell
streamlit run frontend/app.py
```

Opens at http://localhost:8501 — exports Excel locally; nothing persisted.

## v1.1 highlights

- **Confiva-focused:** organizer leads, not sponsorship emails
- **Playwright fallback** for JavaScript-rendered conference sites
- **35+ country/region profiles** with localized queries
- **All event synonyms:** conference, congress, summit, symposium, convention, expo, event, fair (+ local terms)
- **Up to 30 queries per run** (`MAX_QUERIES`)
- **Geo + event filters:** drops news/blog posts, spam domains, stale years
- **One lead per conference:** best organizer contact with quality label
- **Crawl block detection:** returns `CrawlSiteResult` with 403/empty reasons (used by MVP)
- **Manual official URL:** optional override when discovery is thin

## Usage (PoC UI)

1. Pick a **predefined field** (Healthcare, Pharmaceuticals, Security, Cybersecurity, IT, AI).
2. Pick a **predefined region** from the dropdown.
3. Select one or more **months**.
4. Optionally paste a **manual official URL**.
5. Click **Find Leads**.
6. Download the leads Excel file.

Organizer contacts only. Custom region and free-text fields are not in the UI.

## MVP vs PoC

| | PoC (`poc/`) | MVP (`frontend/` + `backend/`) |
|--|--------------|--------------------------------|
| Database | None (session only) | Supabase |
| UI | `poc/frontend/app.py` | `frontend/app.py` (multipage) |
| Pipeline | In-process | API → same `poc/backend` code |
| Blocked sites | Not persisted | `crawl_blocked` in DB + Manual crawl page |
| Review/edit | Debug panel only | Full review UI |

## Deploy to Streamlit Community Cloud (PoC only)

1. Push repo to GitHub.
2. [share.streamlit.io](https://share.streamlit.io) → **Main file:** `poc/frontend/app.py`
3. Python **3.12** (Playwright 1.49 requirement).

Deploy files: `packages.txt`, `poc/frontend/requirements.txt`, `poc/frontend/.streamlit/config.toml`.

**Note:** Cloud IPs may get blocked by some sites. Use **Manual official URL** or run the MVP locally with Supabase.

## Related

- [Root README](../README.md) — MVP setup and run
- [Backend README](../backend/README.md) — API reference
