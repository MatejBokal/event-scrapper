# Conference Contact Finder — PoC v1.1

Local proof-of-concept for **Confiva** ([confiva.com](https://confiva.com/)) sales lead generation.

Finds conference **organizer contacts** by field and region, with evidence-backed export for a separate email outreach tool.

See [docs/poc_v1_spec.md](../docs/poc_v1_spec.md) for the full specification.

## Structure

```text
poc/
  backend/          # pipeline logic
  frontend/         # Streamlit UI
  requirements.txt
  README.md
```

## Setup

```bash
cd poc
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
playwright install chromium
```

## Run

```bash
streamlit run frontend/app.py
```

Opens at http://localhost:8501

## v1.1 highlights

- **Confiva-focused:** organizer leads, not sponsorship emails
- **Playwright fallback** for JavaScript-rendered conference sites
- **35+ country/region profiles** with localized queries
- **Localized queries:** cities + local language (e.g. Slovenian `konferenca`, `kongres`)
- **Geo + event filters:** drops news/blog posts, spam domains, stale years
- **One lead per conference:** best organizer contact with quality label
- **Export:** `confiva_leads_*.csv` / JSON for your email tool

## Usage

1. Enter field (Healthcare, Pharma, Security, IT, AI, or anything).
2. Pick region or use **Custom** for an area/city (e.g. DACH, Bavaria).
3. Set month range for upcoming/recent events.
4. Click **Find Leads**.
5. Download CSV or JSON.

## Notes

- Free stack: DuckDuckGo, requests, BeautifulSoup, trafilatura
- No database, no LLM
- Virtual events are OK if they match region/language signals
- Raw contacts available in debug panel

## Deploy to Streamlit Community Cloud

1. Push this repository to GitHub (public or private).
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
3. Click **New app** and set:
   - **Repository:** your repo
   - **Branch:** `main` (or your default branch)
   - **Main file path:** `poc/frontend/app.py`
4. Open **Advanced settings** and set **Python version to 3.12** (required — Playwright 1.49 does not support 3.14).
5. Click **Deploy**. First boot may take a few minutes (apt packages + Chromium download).
6. Share the `*.streamlit.app` URL.

If the app was already deployed on Python 3.14: open the app **Settings** (⚙️) → change Python version to **3.12** → save and reboot.

Deploy files (already in the repo):

- `packages.txt` — Linux libraries for Playwright Chromium (package names only, no comments)
- `poc/frontend/requirements.txt` — Python dependencies (read by Community Cloud)
- `poc/frontend/.streamlit/config.toml` — Streamlit server settings

**Note:** Search and listing sites may behave differently on cloud IPs than on your PC. Use **Manual official URL** if discovery is thin.
