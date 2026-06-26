# PoC v1.1 — Conference Organizer Lead Finder

Specification for the proof-of-concept app. This document captures everything agreed before and during implementation.

**Related:** [Full MVP blueprint](./conference_organizer_contact_finder_blueprint.md) · [MVP roadmap](./mvp_roadmap.md)

---

## 1. Purpose

Build a **demo-friendly proof of concept** that validates the core hypothesis:

> Can we find conferences for a niche query, crawl their official pages, extract real organizer/contact emails with source evidence, and export usable results — without paying for APIs or building the full MVP stack?

PoC v1 is **not** the MVP. It is a thin vertical slice to prove the pipeline works on real data before investing in FastAPI, PostgreSQL, Next.js, and LLM extraction.

### What PoC v1 must answer

1. **Discovery** — Does search find relevant conferences for a given field, region, and month range?
2. **Site selection** — Can we reach official conference websites (not just listing aggregators)?
3. **Extraction** — Can we pull **organizer** emails from crawled pages without inventing data?
4. **Usefulness** — Are enough results good enough to demo without heavy manual cleanup?

### Success criteria (deferred)

Benchmark validation is planned later. Target bar when we run it:

- At least **3 conferences** with a traceable email per run on a real test query
- Every email linked to a **source URL** and **evidence snippet**
- A full run completes in **under ~5 minutes** on a typical machine
- **Zero cost** — no paid APIs, no API keys required (except optional local tooling)
- User can **download leads** for outreach

---

## 2. Product positioning

Same principle as the full blueprint:

```text
No contact without source evidence.
No invented data.
Confidence score everything.
```

PoC v1 focuses on **emails and evidence**, not rich organizer profiles (names, roles, committees). Those come later via LLM or richer parsing in the MVP.

**Target demo query example:**

```text
Field:    Healthcare          (predefined dropdown)
Region:   Slovenia            (predefined dropdown)
Months:   Jun–Aug 2026        (multi-month picker)
Contact:  organizer           (fixed — Confiva lead gen)
Max:      10 conferences
Optional: manual official URL  (crawl when search is thin)
```

---

## 3. Scope

### In scope (v1 / v1.1)

| Feature | Details |
|---------|---------|
| Streamlit UI | Single-page app: search form + results + download |
| Predefined fields | Dropdown only (Healthcare, Pharmaceuticals, Security, Cybersecurity, IT, AI) |
| Predefined regions | Dropdown from `regions.py` (~35 profiles) |
| Organizer contacts only | Fixed `contact_type=organizer` — Confiva lead gen, no sponsorship/CFP picker |
| Query generation | Up to 18 localized queries per run (month sampling + year fallbacks) |
| Web search | DuckDuckGo via `ddgs` — free, no API key |
| URL scoring | Heuristic official-site picker + listing discovery |
| Manual official URL | Optional text input — crawl directly when search is thin |
| Crawling | `requests` + BeautifulSoup + `trafilatura`; Playwright fallback |
| Extraction | Rule-based: `mailto:`, regex emails, organizer keyword proximity |
| Validation | Email must appear verbatim in crawled page text |
| Confidence | Simple deterministic rules |
| Lead export | Excel download (one lead per conference); raw contacts CSV in debug panel |
| Debug panel | Raw search hits table, crawl targets, listings, filtered/skipped URLs |

### Out of scope (v1 / v1.1)

| Feature | Deferred to |
|---------|-------------|
| Custom region UI | Later (backend hook exists; no form field for now) |
| Free-form field input | Never in PoC — predefined fields only |
| Contact type picker | Never in PoC — organizer only |
| Automated tests | Later |
| Success benchmark runs | Later |
| Database (SQLite/PostgreSQL) | MVP Milestone 1 |
| FastAPI backend | MVP |
| Next.js frontend | MVP |
| LLM extraction (Perplexity Sonar) | v2 / MVP Milestone 4 |
| User authentication | MVP+ |
| Search run history / persistence | MVP |
| Manual edit UI for records | MVP |
| Scheduled / background jobs | MVP+ |
| Full confidence model | MVP |
| Pluggable paid search providers | MVP |
| Rich organizer profiles (LLM) | v2 / MVP Milestone 4 |
| Email outreach | Never in MVP |

---

## 4. Tech stack (100% free)

Everything runs **locally** on the developer's machine.

| Layer | Choice | Cost | Notes |
|-------|--------|------|-------|
| UI | **Streamlit** | $0 | Single `app.py`, run with `streamlit run` |
| Search | **DuckDuckGo** via [`ddgs`](https://pypi.org/project/ddgs/) | $0 | Unofficial scraping; fine at PoC scale |
| HTTP / parse | **requests**, **BeautifulSoup4**, **trafilatura** | $0 | Plain HTTP first |
| JS-rendered sites | **Playwright** (optional fallback) | $0 | Only if plain HTTP fails |
| Export | **csv** / **json** stdlib or **pandas** | $0 | Bytes returned to Streamlit download buttons |
| LLM | **None in v1** | $0 | **Perplexity Sonar** in v2 / Phase 8 if regex is insufficient |

### Services to avoid (paid or quota-limited)

| Service | Why skip for v1 |
|---------|-----------------|
| Bing Search API | Retired; replacement is paid (~$14+/1k queries) |
| SerpAPI | ~100 free searches/month — too limited |
| Google Custom Search | 100 queries/day; requires API setup |
| OpenAI / Anthropic / Groq | Skipped — **Perplexity Sonar** chosen for v2 / Phase 8 |

### Prerequisites

- Python 3.11+
- pip + virtual environment
- (Optional) Playwright browsers: `playwright install` if JS crawling is enabled
- No LLM required for v1 (`PERPLEXITY_API_KEY` only needed for Phase 8)

---

## 5. Pipeline

End-to-end flow for one search run:

```text
┌─────────────────────────────────────────────────────────────┐
│  STREAMLIT UI                                               │
│  field (dropdown), region (dropdown), months, max results   │
│  optional manual official URL                               │
│  [Find Leads]  →  leads table  →  [Download Excel]          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  1. QUERY BUILDER                                           │
│     ~5 queries from user input + contact type               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  2. SEARCH (DuckDuckGo)                                     │
│     ~30–50 raw hits: title, url, snippet, source_query      │
│     stored in memory only                                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  3. URL SCORING                                             │
│     rank likely official sites; denylist aggregators        │
│     optional manual URL override                            │
│     select top N sites (default 5–10)                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  4. CRAWL                                                   │
│     same domain only, depth ≤ 2, max ~10 pages per site     │
│     prefer: contact, sponsors, committee, cfp, about          │
│     extract readable plain text per page                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  5. EXTRACT (rule-based, no LLM)                            │
│     mailto: links, regex emails, keyword proximity          │
│     conference name from <title> / h1 / og:title              │
│     dates/location: best-effort regex only                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  6. VALIDATE + SCORE                                        │
│     email ∈ page text; dedupe; simple confidence            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  7. OUTPUT                                                  │
│     one lead per conference in Streamlit                    │
│     [Download Excel]  debug: raw search hits + raw contacts │
└─────────────────────────────────────────────────────────────┘
```

### Step details

#### 5.1 Query builder

**Input:** `field` (predefined), `region` (predefined), `selected_months`, `contact_type` (fixed: `organizer`)

**Output:** ~5 query strings, e.g.:

```text
AI in healthcare conference Europe 2027
AI in healthcare summit Europe sponsorship contact 2027
AI in healthcare conference sponsors 2027 Europe
AI in healthcare congress exhibitors 2027
AI in healthcare call for papers 2027 Europe
```

v1.1 generates a **small set of month-specific queries** (start / middle / end of range, localized month names) plus year-based fallbacks. Full per-month expansion for every city is deferred to MVP. Keep total queries at `MAX_QUERIES` (18) to respect free DuckDuckGo limits.

#### 5.2 Search

- Library: `ddgs` (`pip install ddgs`)
- ~10 results per query
- Normalize to: `title`, `url`, `snippet`, `source_query`, `rank`
- Add a short delay (1–2 s) between queries to reduce rate-limit risk

#### 5.3 URL scoring

Rank each unique URL. Positive signals:

- URL or title contains field-related keywords
- URL contains event year (e.g. `2027`)
- Domain looks official (not a known aggregator)
- Snippet mentions "conference", "summit", "congress", etc.

Denylist / deprioritize domains such as:

```text
eventbrite.com (listing pages)
meetup.com
10times.com
allconferences.com
conferencealert.com
wiki*
reddit.com
linkedin.com (unless official event page)
```

Allow **manual URL override** in the UI: user pastes an official site URL to crawl directly (skips search for that entry).

#### 5.4 Crawler

Rules (aligned with MVP blueprint, simplified):

```text
- same domain only
- max depth 2
- max 10 pages per conference site
- prefer paths containing: contact, sponsors, sponsorship, committee, organizers, cfp, about
- extract readable text (trafilatura)
- store: url, title, page_type hint, extracted_text
- respect robots.txt where practical
- 1–2 s delay between page fetches
```

Fallback: if `requests` returns empty or JS-shell HTML, retry with Playwright for that URL only.

#### 5.5 Extractor (no LLM)

For each crawled page:

1. **`mailto:` links** — highest confidence
2. **Regex email pattern** on visible text (dedupe, lowercase normalize)
3. **Contact type** from:
   - page URL path (`/sponsors` → `sponsorship`)
   - keywords within ~100 chars of email (`sponsor`, `exhibitor`, `cfp`, `committee`, `contact`)
   - user-selected `contact_type` filter (boost matching rows)
4. **Conference name** — `<title>`, first `<h1>`, or `og:title` from homepage
5. **Dates / location** — optional regex (`2027`, month names); mark low confidence if found

Do **not** infer emails not present in text. Do **not** guess organizer names.

#### 5.6 Validator

```text
- email must appear verbatim in extracted_text (case-insensitive)
- drop malformed emails
- dedupe same email + source_url
- drop pages with no emails (still useful in debug view)
```

#### 5.7 Confidence scoring (simplified)

**Per email row (0–100):**

```text
+40  email found on same domain as conference URL
+20  page path is contact / sponsors / committee / cfp
+20  contact type keyword appears near email
+10  mailto: link (not just regex in footer noise)
+10  not a generic denylisted aggregator source
```

**Caps:**

```text
Listing-site-only source:     max 50
Generic info@ / contact@:     valid, label contact_type as "generic"
No evidence snippet:          do not include row
```

---

## 6. Data model (in-memory only)

No database. Results live in a Python list of dicts for the Streamlit session.

### Search hit (intermediate)

```python
{
    "title": str,
    "url": str,
    "snippet": str,
    "source_query": str,
    "rank": int,
    "url_score": float,       # official-site heuristic
}
```

### Contact result (final export row)

One row per **email found** (not per conference):

```python
{
    "conference_name": str | None,
    "conference_url": str,
    "field": str,
    "region": str,
    "email": str,
    "contact_type": str,          # organizer (PoC); also sponsorship | exhibitor | … internally
    "source_url": str,
    "evidence_snippet": str,      # ~200 chars around the email in page text
    "confidence": int,            # 0–100
    "extraction_method": str,     # "mailto" | "regex" | "regex+keyword"
    "page_title": str | None,
}
```

### Example JSON export

```json
[
  {
    "conference_name": "Health Summit 2027",
    "conference_url": "https://example.com",
    "field": "Healthcare",
    "region": "Slovenia",
    "email": "events@example.com",
    "contact_type": "organizer",
    "source_url": "https://example.com/contact",
    "evidence_snippet": "For event organisation contact events@example.com",
    "confidence": 80,
    "extraction_method": "regex+keyword",
    "page_title": "Contact the organisers"
  }
]
```

### CSV columns

Same fields as JSON, flat one row per email.

---

## 7. UI (Streamlit)

Single page: `poc/frontend/app.py`

### Sections

1. **Search form**
   - Field (dropdown: predefined list in `config.FIELD_OPTIONS`)
   - Region (dropdown: predefined profiles from `regions.py`)
   - Months (multi-select picker: January of current year + 24 months forward)
   - Max conferences (slider: 5–20, default 10)
   - Optional: **manual official URL** (text input — crawled in addition to search results)
   - **Find Leads** button

   Not in the form: custom region, free-form field, contact type (always organizer).

2. **Progress / status**
   - Step indicator: Searching → Scoring → Listing discovery → Crawling → Done
   - Counts: queries, search hits, filtered out, sites crawled, listing discoveries, leads, raw emails

3. **Results table**
   - One row per conference lead: conference, organizer, email, quality, confidence, URL
   - Expandable evidence snippets per lead

4. **Download**
   - **Download leads Excel** (`confiva_leads_YYYYMMDD_HHMMSS.xlsx`)

5. **Debug panel (expandable)**
   - Generated queries
   - **Raw search hits** (table: title, url, snippet, query, rank)
   - Crawl targets (official sites)
   - Listing pages used + warnings + discovered official URLs
   - Filtered out (news/spam/stale) and skipped URLs (low score)
   - Raw contacts CSV download (all emails before lead ranking)

---

## 8. Folder structure

```text
poc/
  backend/
    config.py
    models.py
    pipeline.py
    query_builder.py
    search_ddg.py
    url_scorer.py
    crawler.py
    extractor.py
    validator.py
    confidence.py
    exporter.py
    regions.py
    geo_filter.py
    event_filter.py
    lead_ranker.py
    listing_discovery.py
    domains.py
    playwright_fetcher.py
    cloud_bootstrap.py
  frontend/
    app.py
    requirements.txt
    .streamlit/config.toml
  requirements.txt
  README.md

docs/
  conference_organizer_contact_finder_blueprint.md   # full MVP spec
  poc_v1_spec.md                                     # this document
```

---

## 9. Configuration defaults

```python
MAX_QUERIES = 18
RESULTS_PER_QUERY = 15
MAX_CONFERENCE_SITES = 10
MAX_PAGES_PER_SITE = 10
MAX_CRAWL_DEPTH = 2
REQUEST_DELAY_SECONDS = 1.5
EVIDENCE_SNIPPET_CHARS = 200
LISTING_MAX_PER_RUN = 3
OFFICIAL_LINKS_PER_LISTING = 5
```

---

## 10. Implementation order

Build in slices so each step is testable:

| Step | Build | Status |
|------|-------|--------|
| 1 | Streamlit shell + form + results | Done |
| 2 | Query builder + DuckDuckGo search | Done |
| 3 | URL scoring + geo/event filters | Done |
| 4 | Listing discovery + crawler | Done |
| 5 | Extractor + validator + lead ranker | Done |
| 6 | Confidence + leads table + Excel export | Done |
| 7 | Debug panel (targets, listings, filtered/skipped) | Done |
| 8 | Manual official URL + raw search hits table | Done |
| 9 | Success benchmark on real queries | Deferred |

---

## 11. PoC v1 vs MVP pipeline

| Step | PoC v1 | MVP |
|------|--------|-----|
| UI | Streamlit, one page | Next.js, 5 pages |
| Storage | In-memory → CSV/JSON | PostgreSQL / SQLite |
| Search | DuckDuckGo, ~5 queries | Pluggable provider, many queries |
| Site picking | Heuristics + manual override | `official_site_detector` service |
| Crawl | requests + BS4, ~10 pages/site | Playwright + BS4, stored in DB |
| Extract | Regex, mailto, keywords | LLM → structured JSON |
| People / roles | Skipped | Names, chairs, committees |
| Dates / location | Best-effort regex | LLM + parsing |
| Validation | Email ∈ source text | + JSON schema, evidence checks |
| Confidence | ~6 simple rules | Full conference + organizer model |
| Review | Re-run search | Edit records in UI |
| Export | Excel leads + debug CSV | CSV + XLSX from DB |
| Cost | $0 local | May include paid APIs |

---

## 12. Upgrade path

PoC modules are designed to lift into the MVP backend later:

```text
poc/query_builder.py   →  backend/app/services/query_builder.py
poc/search_ddg.py      →  backend/app/services/search_provider.py
poc/url_scorer.py      →  backend/app/services/official_site_detector.py
poc/crawler.py         →  backend/app/services/crawler.py
poc/extractor.py       →  backend/app/services/extractor.py (add LLM path)
poc/validator.py       →  extraction validation in extractor service
poc/confidence.py      →  backend/app/services/confidence.py
poc/exporter.py        →  backend/app/services/exporter.py
```

### v2 (optional, before full MVP)

Add if regex extraction leaves too many gaps:

- **Perplexity Sonar API** (`PERPLEXITY_API_KEY`) — OpenAI-compatible chat completions
- `disable_search: true` so the model uses only crawled page text (no web lookup)
- Keep same validation: email must appear in source text
- Same Streamlit UI; swap extractor backend when `EXTRACTION_USE_LLM=true`

### MVP milestones (from blueprint)

1. Database + FastAPI CRUD + manual entry + CSV export
2. Search runs without crawling
3. Official site crawling + source evidence in DB
4. LLM extraction + full confidence + review UI
5. Full automated pipeline end-to-end

---

## 13. Known limitations (acceptable for v1 / v1.1)

- Predefined fields and regions only — no custom region or free-text topic in the UI
- Organizer contacts only — no sponsorship / CFP / exhibitor mode
- DuckDuckGo may rate-limit heavy use; keep queries and delays modest
- Regex misses emails embedded only in images or complex JS widgets
- Organizer names are heuristic (regex), not LLM-extracted
- `event_date`, `location`, and `language` in lead export are often empty — acceptable for PoC
- Aggregator sites may still slip through scoring
- Results are lost when the Streamlit session ends (no persistence)
- No automated test suite yet
- Success benchmark not run yet

---

## 14. Legal / compliance (same as blueprint)

- Crawl gently: low frequency, same-domain, respect robots.txt
- Store source URL and evidence snippet for every email
- Prefer business emails (`sponsors@`, `info@`, `events@`)
- Do not auto-email contacts
- GDPR-aware: public data only; plan for removal/opt-out in MVP

---

## 15. How to run (target)

```bash
cd poc
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
streamlit run frontend/app.py
```

Opens at `http://localhost:8501`

---

## 16. Rules for implementation

```text
Do not add a database in PoC.
Do not add an LLM in PoC.
Do not add authentication.
Do not add automated tests yet.
Do not use paid search or LLM APIs.
Do not invent contact data.
Always attach source_url and evidence_snippet to every email.
Predefined fields and regions only — no free-form field or custom region UI.
Organizer contacts only — no contact-type picker.
Prefer working slices over big-bang implementation.
Keep modules small and MVP-liftable.
```

---

## 17. Summary

PoC v1.1 is a **free, local, Streamlit app** that runs:

**search → filter → score → listing discovery → crawl → extract → rank → download Excel**

It proves the Confiva organizer-lead concept without the MVP's database, LLM, or multi-page frontend. Upgrade to LLM and full MVP after benchmark validation on real queries.

---

## 18. v1.1 — Confiva lead generation update

### Business context

PoC v1.1 targets **[Confiva](https://confiva.com/)** sales outreach. Confiva sells an event platform to **conference organizers**. The tool is a **lead generator** for finding organizer contacts to pitch the platform — not sponsorship or exhibitor contacts.

**Ideal leads:**
- Upcoming conferences (6+ months out) or recently ended (≤ 1.5 months ago)
- Named organizer / event manager email preferred over `info@`
- Virtual events OK if region/language match (e.g. Slovenian virtual event for Slovenia search)
- Export feeds a **separate email outreach tool** later

**Predefined fields** (dropdown in `config.FIELD_OPTIONS`): Healthcare, Pharmaceuticals, Security, Cybersecurity, IT, AI.

### Region support

Built-in region profiles in `backend/regions.py` (~35 countries/macros). User picks from a **dropdown only**.

| Examples | Cities | Languages |
|----------|--------|-----------|
| Slovenia | Ljubljana, Maribor, Celje, … | en, sl |
| Croatia | Zagreb, Split, Rijeka, … | en, hr |
| Germany | Berlin, Munich, Hamburg, … | en, de |
| United Kingdom | London, Manchester, … | en |
| Europe | Brussels, Amsterdam, Paris, … | en |
| Worldwide | — | en |

**Custom region** (user-entered area like DACH or Bavaria) is deferred — backend has a hook (`custom_region`) but the UI does not expose it yet.

### v1.1 pipeline changes

```text
search (localized query expansion)
  → event filter (drop news/blogs/spam/stale years)
  → geo scoring (.si, cities, phone prefixes, negative locations)
  → site selection (minimum geo score; listing pages allowed)
  → listing discovery (Eventbrite, 10times, etc. → outbound official URLs)
  → crawl official sites only (organizer-focused pages)
  → extract + validate (never keep emails from listing domains)
  → lead ranker (one best contact per conference)
  → export leads Excel (+ raw contacts CSV in debug)
```

### Listing-site discovery (v1.1.1)

Aggregator/listing domains (Eventbrite, Meetup, 10times, AllConferences, ConferenceAlert, etc.) are **discovery sources only**:

1. Search may select up to **3 listing pages** per run (`LISTING_MAX_PER_RUN`).
2. Each listing page is fetched once (HTTP + Playwright fallback).
3. Outbound links are scored for conference signals (field keywords, regional TLD/city, year, “official website” anchor text).
4. Up to **5 official URLs per listing** (`OFFICIAL_LINKS_PER_LISTING`) are added to the crawl queue.
5. **Contacts are never extracted from listing domains** — only from discovered official conference sites.

Hard-dropped spam farms (`waset.org`, `mindauthors.com`, …) remain blocked at the event-filter stage and are never followed as outbound links.

New module: `backend/listing_discovery.py` + shared domain helpers in `backend/domains.py`.

### Query expansion (replaces manual city searches)

Automates variations like:
- `healthcare conference Ljubljana June 2026`
- `zdravstvo konferenca Ljubljana junij 2026`
- `healthcare organizator Ljubljana junij 2026`
- `healthcare conference Ljubljana 2026` (year fallback)

Month queries sample **start, middle, and end** months from the selected range (up to 3), using localized month names (`June` / `junij`, etc.). Up to **6 query slots** are reserved for month variants; the rest stay year/location/organizer queries.

Interleaves languages per region up to `MAX_QUERIES` (18).

### Lead export schema

One row per conference:

```csv
conference_name,conference_url,event_date,location,field,region,
organizer_name,organizer_email,organizer_role,contact_quality,
source_url,evidence_snippet,confidence,language
```

`contact_quality`: `named_organizer` | `role_email` | `generic_info` | `unknown`

`language` is included in the schema but may be `null` — no extra extraction work planned for PoC.

### New backend modules

```text
backend/regions.py           # region profiles + field translations
backend/geo_filter.py        # geo relevance scoring
backend/event_filter.py      # news/spam/stale filtering
backend/lead_ranker.py       # one lead per conference, organizer priority
backend/listing_discovery.py # resolve official URLs from listing pages
backend/domains.py           # listing vs spam vs blocked domain helpers
```

### Known v1.1 limitations

- Date parsing is still basic (year-level filtering only)
- Organizer name extraction is heuristic (regex), not LLM
- DuckDuckGo rate limits still apply at scale
- Adding a new country = add a `RegionProfile` entry in `regions.py`
- No automated tests; success benchmark deferred

### Remaining PoC work (agreed)

| Item | Status |
|------|--------|
| Manual official URL (form + pipeline) | Done |
| Raw search hits table in debug panel | Done |
| Custom region UI | Deferred |
| Free-form field input | Out of scope |
| Contact type picker | Out of scope (organizer only) |
| Automated tests | Deferred |
| Success benchmark (3+ leads, &lt;5 min) | Deferred |
