# MVP Roadmap — Conference Organizer Lead Finder

Phased plan to evolve the **PoC v1.1** into a **production MVP** for Confiva sales lead generation.

**Related docs:**

- [PoC v1.1 spec](./poc_v1_spec.md) — pipeline behaviour and rules
- [Full blueprint](./conference_organizer_contact_finder_blueprint.md) — long-term product vision
- [Root README](../README.md) — how to run the MVP today

---

## 1. Where we are now

| Area | Status |
|------|--------|
| PoC pipeline | Done — search → filter → crawl → extract → rank |
| PoC Streamlit | Done — standalone in `poc/frontend/` (legacy) |
| **MVP Streamlit app** | Done — `frontend/` (Find / Review / Manual crawl) |
| Database | Done — Supabase `nqtocnlrzsgkcetdrebh`, all migrations applied |
| FastAPI | Done — v0.7.0 (CRUD, search runs, full pipeline, export) |
| Full pipeline in DB | Done — search + crawl + extract + organizers + evidence |
| Review / edit UI | Done — filters, detail, verify/reject, export |
| Crawl block-list | Done — `crawl_blocked` status + Manual crawl page |
| Auth + RLS (user-scoped) | Not started (Phase 7) |
| LLM extraction | Not started (Phase 8) |
| Success benchmark | Deferred |
| Background `/execute` | Not started — runs synchronously in HTTP request |

**MVP core workflow works:** run search → review leads → fix bad data → export Excel from DB.

---

## 2. MVP definition of done

The MVP is complete when a user can:

1. Run a search (field, region, months, optional manual URL). ✅
2. See progress and results stored in **Supabase**. ✅
3. Browse conferences and organizer leads with **source evidence**. ✅
4. **Manually correct** bad records (email, name, status). ✅
5. **Export** leads to Excel from the database. ✅
6. Re-open past search runs and compare results. ✅ (via API / Supabase)
7. Handle **blocked crawls** manually via Manual crawl page. ✅

**Still out of scope for MVP:**

- Free-form field input (predefined fields only)
- Contact type picker (organizer only)
- Custom region UI
- Automated email outreach
- Multi-tenant SaaS / billing
- Scheduled background jobs
- Paid search APIs

---

## 3. Target stack (as built)

| Layer | Choice | Location |
|-------|--------|----------|
| Database | Supabase PostgreSQL | `supabase/migrations/` |
| Backend | FastAPI 0.7 | `backend/app/` |
| Pipeline | PoC modules via `poc_bridge` | `poc/backend/` |
| Secrets | `.env` | `DATABASE_URL` |
| Frontend | Streamlit 1.36+ multipage | `frontend/` |
| Crawler | requests + BS4 + trafilatura + Playwright | `poc/backend/crawler.py` |
| Search | DuckDuckGo via `ddgs` | `poc/backend/search_ddg.py` |
| Auth | Deferred | Phase 7 |

**Access rule:** pipeline and bulk writes use `DATABASE_URL` on the server only.

---

## 4. Current folder structure

```text
EventOrganiser Scrapper/
  .env                          # secrets (gitignored)
  README.md                     # start here
  docs/
    poc_v1_spec.md
    mvp_roadmap.md
    conference_organizer_contact_finder_blueprint.md
  poc/                          # pipeline source (also standalone PoC)
    backend/
    frontend/                   # legacy Streamlit
  backend/                      # FastAPI MVP
    app/
      main.py
      api/                      # conferences, organizers, search_runs, export
      models.py
      schemas/
      services/
        poc_bridge.py
        search_run.py
        crawl_run.py
        extract_run.py
        pipeline_run.py
        exporter.py
  frontend/                     # MVP Streamlit app
    app.py
    pages/
    lib/
    api_client.py
  supabase/
    migrations/
  scripts/                      # migrations, smoke tests
```

---

## 5. Database schema (Supabase)

### Core

| Table | Purpose |
|-------|---------|
| `search_runs` | One pipeline job; params + status/stats/errors |
| `conferences` | Event record; dedupe on `official_url_normalized` |
| `organizers` | All contacts + `is_primary_lead` for export |
| `source_evidence` | Required audit trail per email |

### Pipeline audit

| Table | Purpose |
|-------|---------|
| `search_queries` | Generated queries per run |
| `search_results` | Raw search hits |
| `crawl_targets` | Selected / manual / listing-discovered URLs |
| `crawled_pages` | Fetched pages + extracted text |

### Conference statuses

`discovered`, `official_site_found`, `crawled`, `extracted`, `crawl_blocked`, `needs_review`, `verified`, `rejected`

### Crawl block metadata (on `conferences`)

`crawl_block_reason`, `crawl_http_status`, `crawl_block_detail`, `crawl_blocked_at`

Blocked URLs are **skipped on future auto-crawls** until `POST /api/conferences/{id}/retry-crawl`.

### Conventions

- **Dedupe:** `official_url_normalized` unique on `conferences`
- **Lead:** one `is_primary_lead = true` organizer per conference (export)
- **RLS:** enabled, deny-all until Phase 7

---

## 6. Phases

### Phase 0 — Gate (optional) — ⏸ Deferred

Success benchmark not run yet.

---

### Phase 1 — Supabase foundation — ✅ Done

Migration: `20260412160000_initial_schema.sql`

---

### Phase 2 — FastAPI + manual CRUD — ✅ Done

CRUD, evidence on create, Excel export.

---

### Phase 3 — Search runs — ✅ Done

Migration: `20260426140000_search_audit_tables.sql`  
`POST/GET /api/search-runs`, queries + raw hits in DB.

---

### Phase 4 — Crawl + evidence — ✅ Done

Migration: `20260426150000_crawl_tables.sql`  
`POST /api/search-runs/{id}/crawl`, pages + evidence in DB.

---

### Phase 5 — Full pipeline integration — ✅ Done

- `extract_run.py`, `pipeline_run.py`
- `POST /api/search-runs/{id}/execute`
- `POST /api/search-runs` with `execute_search`, `execute_crawl`, `execute_extract`
- Organizers + evidence from extraction
- Smoke test: `scripts/smoke_test_execute.py`

---

### Phase 6 — Review UI — ✅ Done

- `frontend/` Streamlit app with sidebar navigation
- Pages: Find leads, Review leads, Manual crawl, Conference detail
- Filters: field, region, status, has_email
- Edit conference / organizer; verify / reject
- Export from sidebar

---

### Phase 6b — Crawl block-list + manual review — ✅ Done

Migration: `20260427120000_crawl_blocked.sql`

- `CrawlSiteResult` in PoC crawler (403, empty, etc.)
- Persist `crawl_blocked` conferences; skip on future crawls
- Manual crawl page + `retry-crawl` API
- Expanded query synonyms (30 queries max)

---

### Phase 7 — Auth + RLS (when needed) — 🔜 Next

| Task | Deliverable |
|------|-------------|
| Supabase Auth | Email login or magic link |
| `user_id` on `search_runs` | Optional `organization_id` later |
| RLS policies | `auth.uid() = user_id` |
| Frontend uses publishable key only | |

**Exit criteria:** Users only see their own runs and conferences.

---

### Phase 8 — Post-MVP (not blocking)

| Item | When |
|------|------|
| Background job queue for `/execute` | Long runs block HTTP today |
| LLM extraction (Ollama / API) | If regex leaves too many gaps |
| Custom region UI | When sales needs DACH etc. |
| Automated tests + CI | Quality gate for releases |
| Scheduled searches | Cron / Supabase pg_cron |
| Paid search providers | Scale beyond DuckDuckGo |
| Next.js frontend | If Streamlit limits UX |
| Email outreach module | Separate tool; feed from export |

---

## 7. PoC → MVP lift map (actual)

| `poc/backend/` module | MVP usage today |
|-----------------------|-----------------|
| All pipeline modules | Loaded via `backend/app/services/poc_bridge.py` |
| `pipeline.py` | PoC Streamlit + reference; MVP uses `search_run` + `crawl_run` + `extract_run` |
| SQLAlchemy models | `backend/app/models.py` (separate from PoC dataclasses) |
| `poc/frontend/app.py` | Legacy; replaced by `frontend/app.py` for MVP |

**Strategy:** keep `poc/` working; MVP imports it rather than duplicating.

---

## 8. Decisions locked for MVP

| Decision | Choice |
|----------|--------|
| Database | Supabase PostgreSQL |
| Primary contact type | Organizer only |
| Fields / regions | Predefined dropdowns only |
| One lead per conference | `is_primary_lead` on best organizer row |
| Store raw contacts | All emails in `organizers` |
| Dedupe conferences | By `official_url_normalized` |
| Evidence | Required for emails |
| Blocked crawls | Persist + skip + manual review |
| Daily UI | `frontend/` Streamlit app |

---

## 9. Build order (summary)

```text
Phase 0  Validate PoC          ⏸ deferred
Phase 1  Supabase schema       ✅
Phase 2  FastAPI CRUD          ✅
Phase 3  Search runs           ✅
Phase 4  Crawl                 ✅
Phase 5  Full pipeline          ✅
Phase 6  Review UI             ✅
Phase 6b Crawl block-list      ✅
Phase 7  Auth + RLS            🔜 next
Phase 8  LLM, tests, jobs      post-MVP
```

---

## 10. Next actionable tasks

1. **Use it** — run real field/region combos; validate lead quality for Confiva sales.
2. **Phase 7** — when you need hosted multi-user access.
3. **Optional polish** — background `/execute`, CI smoke tests, deploy API + Streamlit.

---

## 11. Rules (carry forward from PoC)

```text
No contact without source evidence.
No invented data.
Confidence score everything.
Service role only on server.
Do not expose database password or service role to frontend.
Prefer small phases over big-bang.
Keep poc/ working — MVP imports it via poc_bridge.
```
