-- Phase 3: search audit tables

create table public.search_queries (
  id uuid primary key default gen_random_uuid(),
  search_run_id uuid not null references public.search_runs (id) on delete cascade,
  query_text text not null,
  order_index int not null
);

create index idx_search_queries_run_id on public.search_queries (search_run_id);

create table public.search_results (
  id uuid primary key default gen_random_uuid(),
  search_run_id uuid not null references public.search_runs (id) on delete cascade,
  title text,
  url text not null,
  snippet text,
  source_query text,
  rank int,
  url_score numeric,
  filter_status text
);

create index idx_search_results_run_id on public.search_results (search_run_id);
create index idx_search_results_url on public.search_results (url);

alter table public.search_queries enable row level security;
alter table public.search_results enable row level security;

create policy "deny_all_search_queries" on public.search_queries
  for all using (false);

create policy "deny_all_search_results" on public.search_results
  for all using (false);
