# Supabase — Event Organiser Lead Finder

**Project ref:** `nqtocnlrzsgkcetdrebh`  
**Credentials:** repo-root `.env` (not committed)

## Apply migrations

```powershell
python scripts/apply_migrations.py
```

## Tables (Phase 1–3)

- `search_runs`, `search_queries`, `search_results`
- `crawl_targets`, `crawled_pages`
- `conferences`, `organizers`, `source_evidence`

RLS enabled with deny-all policies. Server code uses `SUPABASE_SERVICE_ROLE_KEY` or `DATABASE_URL`.

## CLI (optional)

```powershell
supabase link --project-ref nqtocnlrzsgkcetdrebh
supabase db push
```
