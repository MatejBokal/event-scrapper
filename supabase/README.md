# Supabase — Event Organiser Lead Finder

**Project ref:** `nqtocnlrzsgkcetdrebh`  
**Credentials:** repo-root `.env` (not committed)

## Apply migrations

```powershell
python scripts/apply_migrations.py
python scripts/verify_schema.py
```

## Migrations

| File | Contents |
|------|----------|
| `20260412160000_initial_schema.sql` | Core tables + RLS |
| `20260426140000_search_audit_tables.sql` | `search_queries`, `search_results` |
| `20260426150000_crawl_tables.sql` | `crawl_targets`, `crawled_pages` |
| `20260427120000_crawl_blocked.sql` | `crawl_blocked` status + block metadata columns |

## Tables

| Table | Purpose |
|-------|---------|
| `search_runs` | Pipeline jobs (params, status, stats, errors) |
| `search_queries` | Generated queries per run |
| `search_results` | Raw search hits |
| `crawl_targets` | URLs selected for crawl |
| `crawled_pages` | Fetched page text |
| `conferences` | Events; dedupe on `official_url_normalized` |
| `organizers` | Contacts; `is_primary_lead` for export |
| `source_evidence` | Required audit trail per email |
| `schema_migrations` | Applied migration tracking (custom) |

### Conference block metadata (migration 4)

- `crawl_block_reason` — e.g. `http_403`, `empty`, `fetch_failed`
- `crawl_http_status` — HTTP status when known
- `crawl_block_detail` — error message snippet
- `crawl_blocked_at` — timestamp

Status `crawl_blocked` means skip auto-crawl until cleared via API.

## Access

RLS enabled with deny-all policies. Backend uses `DATABASE_URL` (service role / direct Postgres). Never expose credentials to the browser.

## CLI (optional)

```powershell
supabase link --project-ref nqtocnlrzsgkcetdrebh
supabase db push
```

Prefer `python scripts/apply_migrations.py` for consistent `schema_migrations` tracking.
