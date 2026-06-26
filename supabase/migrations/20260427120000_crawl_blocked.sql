-- Track sites that block automated crawl (403, empty, etc.) for manual review.

alter table public.conferences drop constraint if exists conferences_status_check;

alter table public.conferences
  add constraint conferences_status_check
  check (status in (
    'discovered',
    'official_site_found',
    'crawled',
    'extracted',
    'needs_review',
    'verified',
    'rejected',
    'crawl_blocked'
  ));

alter table public.conferences
  add column if not exists crawl_block_reason text,
  add column if not exists crawl_http_status int,
  add column if not exists crawl_block_detail text,
  add column if not exists crawl_blocked_at timestamptz;

create index if not exists idx_conferences_crawl_blocked
  on public.conferences (crawl_blocked_at desc)
  where status = 'crawl_blocked';
