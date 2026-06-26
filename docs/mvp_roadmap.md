# MVP Roadmap — Conference Organizer Lead Finder

Phased plan to evolve the **PoC v1.1** into a **production MVP** for Confiva sales lead generation.

**Related docs:**

- [PoC v1.1 spec](./poc_v1_spec.md) — what is built today
- [Full blueprint](./conference_organizer_contact_finder_blueprint.md) — long-term product vision
- `.env.example` — Supabase credentials (copy to `.env`)

---

## 1. Where we are now

| Area | Status |
|------|--------|
| PoC pipeline | Done — search → filter → crawl → extract → rank |
| Streamlit UI | Done — predefined fields/regions, manual URL, Excel export |
| Database | Done — Supabase `nqtocnlrzsgkcetdrebh`, Phase 1 tables + RLS |
| FastAPI | Done — Phases 2–4 (CRUD, search runs, crawl persistence) |
| Persistence | Search + crawl in DB; full pipeline extraction not wired yet |
| Auth | Not started |
| LLM extraction | **Perplexity Sonar** — wired; enable with `PERPLEXITY_API_KEY` |
| Success benchmark | Deferred |

**PoC proves:** we can find organizer emails with source evidence on real queries.

**MVP must add:** store runs, review/edit leads, export from DB, survive restarts, and support a real Confiva workflow.

---

## 2. MVP definition of done

The MVP is complete when a user can:

1. Run a search (field, region, months, optional manual URL).
2. See progress and results stored in **Supabase** (not just session memory).
3. Browse conferences and organizer leads with **source evidence**.
4. **Manually correct** bad records (email, name, status).
5. **Export** leads to Excel/CSV from the database.
6. Re-open past search runs and compare results.

**Still out of scope for MVP:**

- Free-form field input (predefined fields only)
- Contact type picker (organizer only)
- Custom region UI
- Automated email outreach
- Multi-tenant SaaS / billing
- Scheduled background jobs (manual trigger only)
- Paid search APIs

**Optional before MVP (gate):**

- PoC success benchmark (3+ leads with evidence, &lt;5 min)
- PoC v2 with **Perplexity** LLM extraction if regex extraction is too weak

---

## 3. Target stack

| Layer | Choice | Notes |
|-------|--------|-------|
| Database | **Supabase (PostgreSQL)** | Migrations in `supabase/migrations/` |
| Backend | **FastAPI** | Server-side pipeline + CRUD |
| Pipeline | **Lift `poc/backend/`** | Reuse modules; move to `backend/app/services/` |
| Secrets | **`.env`** | `DATABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` |
| Frontend (MVP) | **Streamlit → Next.js** | Keep Streamlit calling API first; Next.js when review UI needs grow |
| Crawler | requests + BS4 + trafilatura + Playwright | Same as PoC |
| Search | DuckDuckGo via `ddgs` | Free; paid providers later |
| LLM | **Perplexity Sonar** (Phase 8) | Regex default; `EXTRACTION_USE_LLM=true` when wired |
| Auth | Supabase Auth (Phase 7) | RLS after single-user MVP works |

**Access rule:** pipeline and bulk writes use **service role** or direct Postgres URL on the server only. Never expose service role to the browser.

---

## 4. Target folder structure

```text
EventOrganiser Scrapper/
  .env                          # secrets (gitignored)
  .env.example
  docs/
    poc_v1_spec.md
    mvp_roadmap.md              # this file
    conference_organizer_contact_finder_blueprint.md
  poc/                          # keep until API replaces Streamlit entry
    backend/                    # pipeline logic (lift into backend/)
    frontend/                   # Streamlit PoC UI
  backend/                      # NEW — FastAPI MVP
    app/
      main.py
      config.py
      database.py
      models/                   # SQLAlchemy or raw SQL via asyncpg
      schemas/                  # Pydantic
      api/
        search_runs.py
        conferences.py
        organizers.py
        export.py
      services/
        persist_run.py          # PipelineResult → Supabase
        query_builder.py        # ← from poc/backend
        pipeline.py             # ← from poc/backend
        ...
    requirements.txt
  supabase/
    config.toml
    migrations/
  frontend/                     # NEW — Next.js (Phase 6+)
```

---

## 5. Database schema (Supabase)

### Phase 1 — core tables

| Table | Purpose |
|-------|---------|
| `search_runs` | One user job; maps to `SearchParams` + status/stats/errors |
| `conferences` | Event record; dedupe on `official_url_normalized` |
| `organizers` | All contacts + `is_primary_lead` for ranked lead |
| `source_evidence` | Required audit trail per email |

### Phase 3 — pipeline audit

| Table | Purpose |
|-------|---------|
| `search_queries` | Generated queries per run |
| `search_results` | Raw search hits (debug table persisted) |
| `crawl_targets` | Selected / manual / listing-discovered URLs |
| `crawled_pages` | Fetched pages + extracted text |

### Key conventions

- **IDs:** `uuid` + `gen_random_uuid()`
- **Dedupe:** normalize URL → unique `official_url_normalized` on `conferences`
- **Lead:** one `organizers` row with `is_primary_lead = true` per conference per run
- **RLS:** enabled on all `public` tables; deny-all until Auth (Phase 7)

See Phase 1 migration task for full SQL.

---

## 6. Phases

### Phase 0 — Gate (optional but recommended)

**Goal:** Confirm PoC quality before building persistence.

| Task | Deliverable |
|------|-------------|
| Run benchmark queries | Healthcare + Slovenia, 3 months; log leads, time, evidence |
| Review lead quality | Decide: proceed to MVP or add PoC v2 (Perplexity LLM) first |
| Document results | Short note in repo or issue |

**Exit criteria:** Team agrees extraction is good enough to store and sell against, or v2 is scoped.

---

### Phase 1 — Supabase foundation

**Goal:** Database exists; schema in git; secrets wired.

| Task | Deliverable |
|------|-------------|
| `supabase init` + link project | `supabase/config.toml` |
| Migration: core 4 tables | `supabase/migrations/..._initial_schema.sql` |
| Indexes + `updated_at` trigger on `conferences` | In migration |
| Enable RLS + deny-all policies | In migration |
| Fill `.env` | Working `DATABASE_URL` + service role key |
| Verify connection | Simple script or `psql` smoke test |

**Exit criteria:** Can insert a conference + organizer + evidence row manually in Supabase SQL editor.

---

### Phase 2 — FastAPI + manual CRUD

**Goal:** Validate data model without scraping. Blueprint Milestone 1.

| Task | Deliverable |
|------|-------------|
| FastAPI app skeleton | `backend/app/main.py` |
| SQLAlchemy/asyncpg + models | Match Phase 1 schema |
| CRUD API | `GET/POST/PATCH /conferences`, `/organizers` |
| Evidence on create/update | `source_evidence` required when email is set |
| Export endpoint | `GET /export/leads.xlsx` from DB |
| Minimal test client | curl, HTTPie, or Streamlit page calling API |

**Exit criteria:** Manually create 2 conferences with organizers and evidence; download Excel export.

---

### Phase 3 — Search runs (no crawl yet)

**Goal:** Persist discovery. Blueprint Milestone 2.

| Task | Deliverable |
|------|-------------|
| Migration: audit tables | `search_queries`, `search_results` |
| `POST /search-runs` | Create run from form params |
| Wire `search_ddg` + `query_builder` | Store queries + raw hits |
| `GET /search-runs/{id}` | Status, hits, stats |
| Streamlit or API client | Trigger search-only run |

**Exit criteria:** Search run stored in DB; raw hits visible via API; no crawl yet.

---

### Phase 4 — Crawl + evidence in DB

**Goal:** Persist crawl artifacts. Blueprint Milestone 3.

| Task | Deliverable |
|------|-------------|
| Migration: `crawl_targets`, `crawled_pages` | |
| Lift crawler into `backend/app/services/` | From `poc/backend/crawler.py` |
| Store crawled pages + evidence | Link to `conference_id` |
| Conference upsert on crawl | By `official_url_normalized` |

**Exit criteria:** Crawl targets and page text stored; evidence rows linked in DB.

---

### Phase 5 — Full pipeline integration

**Goal:** End-to-end automated run into Supabase. Blueprint Milestone 5.

| Task | Deliverable |
|------|-------------|
| Lift full `poc/backend/pipeline.py` | Into `backend/app/services/` |
| `persist_run.py` | Map `PipelineResult` → all tables |
| `POST /search-runs/{id}/execute` | Async or background task |
| Status updates on `search_runs` | `pending` → `running` → `completed` / `failed` |
| Streamlit calls API | Or replace with thin API client |
| Error + stats JSON on run row | Same as PoC debug data |

**Exit criteria:** One API call runs full pipeline; leads appear in `conferences` + `organizers`; export works.

---

### Phase 6 — Review UI

**Goal:** Human can fix bad data. Blueprint Milestone 4 (UI part).

| Task | Deliverable |
|------|-------------|
| Conference list with filters | field, region, status, has email |
| Conference detail page | organizers, evidence, crawl history |
| Edit forms | PATCH conference / organizer |
| Mark verified / rejected | Status workflow |
| Next.js app (or extended Streamlit) | `frontend/` |

**Exit criteria:** User finds a bad email, edits it, re-exports; evidence still visible.

---

### Phase 7 — Auth + RLS (when needed)

**Goal:** Secure multi-user or hosted deploy.

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
| LLM extraction (**Perplexity Sonar**) | If regex leaves too many gaps — see § Phase 8 design below |
| Custom region UI | When sales needs DACH etc. |
| Automated tests | CI for API + persist layer |
| Scheduled searches | Cron / Supabase pg_cron |
| Paid search providers | Scale beyond DuckDuckGo |
| Email outreach module | Separate tool; feed from export |

**Phase 8 LLM design (locked):**

| Item | Choice |
|------|--------|
| Provider | **Perplexity Sonar API** ([OpenAI-compatible](https://docs.perplexity.ai/docs/sonar/openai-compatibility)) |
| Env | `PERPLEXITY_API_KEY`, optional `PERPLEXITY_MODEL` (default `sonar`) |
| Toggle | Enabled when `PERPLEXITY_API_KEY` is set; set `EXTRACTION_USE_LLM=false` to disable |
| Input | Crawled page text only (same as blueprint §9) |
| API flags | `disable_search: true` — must not web-search; only use provided `PAGE_TEXT` |
| Page selection | Top **3** scored pages per site — **one combined API call** fills conference + organizers |
| Persisted fields | Conference: name, dates, location, country, description, language. Organizer: name, role, org, phone, website, LinkedIn |
| Output | JSON organizers + conference fields; same validator as regex (email in source text) |
| Fallback | Regex extraction when key missing, flag off, or LLM call fails |

Ollama / local LLM: **skipped** — Perplexity only.

---

## 7. PoC → MVP lift map

| `poc/backend/` module | MVP location |
|-----------------------|--------------|
| `pipeline.py` | `backend/app/services/pipeline.py` |
| `query_builder.py` | `backend/app/services/query_builder.py` |
| `search_ddg.py` | `backend/app/services/search_provider.py` |
| `url_scorer.py` | `backend/app/services/official_site_detector.py` |
| `listing_discovery.py` | `backend/app/services/listing_discovery.py` |
| `crawler.py` | `backend/app/services/crawler.py` |
| `extractor.py` | `backend/app/services/extractor.py` |
| `validator.py` | `backend/app/services/validator.py` |
| `confidence.py` | `backend/app/services/confidence.py` |
| `lead_ranker.py` | `backend/app/services/lead_ranker.py` |
| `exporter.py` | `backend/app/services/exporter.py` |
| `regions.py`, `domains.py`, … | `backend/app/services/` or `backend/app/lib/` |
| `models.py` (dataclasses) | Keep for pipeline; add SQLAlchemy models separately |
| `poc/frontend/app.py` | API client → later `frontend/` |

**Strategy:** copy modules incrementally; run PoC and MVP side by side until Phase 5 cutover.

---

## 8. Decisions locked for MVP

| Decision | Choice |
|----------|--------|
| Database | Supabase PostgreSQL |
| Primary contact type | Organizer only (Confiva leads) |
| Fields | Predefined dropdown only |
| Regions | Predefined dropdown only (custom region later) |
| One lead per conference | `is_primary_lead` on best organizer row |
| Store raw contacts | Yes — all emails in `organizers`, not only the lead |
| Dedupe conferences | By normalized `official_url` across runs |
| Evidence | Required — no email without `source_evidence` row |
| LLM provider (Phase 8) | **Perplexity Sonar** — not Ollama |
| PoC Streamlit | Keep until Phase 5/6 API client is ready |

---

## 9. Suggested build order (summary)

```text
Phase 0  Validate PoC (optional gate)
Phase 1  Supabase schema + migrations + .env
Phase 2  FastAPI CRUD + manual entry + export
Phase 3  Search runs → DB (search only)
Phase 4  Crawl + evidence → DB
Phase 5  Full pipeline → DB (automated MVP core)
Phase 6  Review / edit UI
Phase 7  Auth + RLS
Phase 8  Perplexity LLM extraction, tests, scheduling (post-MVP)
```

**Start here:** Phase 5 (full pipeline → DB: extract, rank, leads).

---

## 10. Next actionable task

1. Create Supabase project (if not done).
2. `supabase init` in repo root.
3. Add migration `initial_schema` with 4 core tables + RLS.
4. Apply to remote project.
5. Smoke-test insert from SQL editor.

After that → Phase 2 FastAPI skeleton.

---

## 11. Rules (carry forward from PoC)

```text
No contact without source evidence.
No invented data.
Confidence score everything.
Service role only on server.
Do not expose database password or service role to frontend.
Prefer small phases over big-bang.
Keep poc/ working until MVP pipeline is proven.
```
