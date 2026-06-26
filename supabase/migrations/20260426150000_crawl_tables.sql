-- Phase 4: crawl targets and crawled pages

create table public.crawl_targets (
  id uuid primary key default gen_random_uuid(),
  search_run_id uuid not null references public.search_runs (id) on delete cascade,
  conference_id uuid references public.conferences (id) on delete set null,
  url text not null,
  title text,
  source text,
  discovered_from text,
  url_score numeric
);

create index idx_crawl_targets_run_id on public.crawl_targets (search_run_id);
create index idx_crawl_targets_conference_id on public.crawl_targets (conference_id);

create table public.crawled_pages (
  id uuid primary key default gen_random_uuid(),
  conference_id uuid not null references public.conferences (id) on delete cascade,
  search_run_id uuid references public.search_runs (id) on delete set null,
  url text not null,
  title text,
  page_type text,
  extracted_text text,
  crawled_at timestamptz not null default now()
);

create index idx_crawled_pages_conference_id on public.crawled_pages (conference_id);
create index idx_crawled_pages_run_id on public.crawled_pages (search_run_id);

alter table public.crawl_targets enable row level security;
alter table public.crawled_pages enable row level security;

create policy "deny_all_crawl_targets" on public.crawl_targets
  for all using (false);

create policy "deny_all_crawled_pages" on public.crawled_pages
  for all using (false);
