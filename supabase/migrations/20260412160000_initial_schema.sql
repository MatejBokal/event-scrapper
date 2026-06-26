-- Phase 1: core tables for Conference Organizer Lead Finder MVP

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------------
-- search_runs
-- ---------------------------------------------------------------------------
create table public.search_runs (
  id uuid primary key default gen_random_uuid(),
  field text not null,
  region text not null,
  selected_months text[] not null default '{}',
  contact_type text not null default 'organizer',
  max_conferences int not null default 10,
  manual_official_url text,
  status text not null default 'pending'
    check (status in ('pending', 'running', 'completed', 'failed', 'cancelled')),
  stats jsonb not null default '{}',
  errors jsonb not null default '[]',
  created_at timestamptz not null default now(),
  finished_at timestamptz
);

create index idx_search_runs_created_at on public.search_runs (created_at desc);

-- ---------------------------------------------------------------------------
-- conferences
-- ---------------------------------------------------------------------------
create table public.conferences (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  field text,
  region text,
  start_date date,
  end_date date,
  month_year text,
  location text,
  country text,
  official_url text not null,
  official_url_normalized text not null,
  description text,
  status text not null default 'discovered'
    check (status in (
      'discovered',
      'official_site_found',
      'crawled',
      'extracted',
      'needs_review',
      'verified',
      'rejected'
    )),
  confidence_score int not null default 0,
  first_seen_run_id uuid references public.search_runs (id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint conferences_official_url_normalized_unique unique (official_url_normalized)
);

create index idx_conferences_status on public.conferences (status);
create index idx_conferences_field on public.conferences (field);
create index idx_conferences_region on public.conferences (region);

-- ---------------------------------------------------------------------------
-- organizers
-- ---------------------------------------------------------------------------
create table public.organizers (
  id uuid primary key default gen_random_uuid(),
  conference_id uuid not null references public.conferences (id) on delete cascade,
  search_run_id uuid references public.search_runs (id) on delete set null,
  name text,
  organization text,
  role text,
  email text not null,
  phone text,
  website text,
  linkedin_url text,
  contact_type text not null default 'organizer',
  contact_quality text
    check (contact_quality in ('named_organizer', 'role_email', 'generic_info', 'unknown')),
  is_primary_lead boolean not null default false,
  confidence_score int not null default 0,
  extraction_method text,
  created_at timestamptz not null default now()
);

create index idx_organizers_conference_id on public.organizers (conference_id);
create index idx_organizers_email on public.organizers (email);
create unique index idx_organizers_primary_lead_per_run
  on public.organizers (conference_id, search_run_id)
  where is_primary_lead = true and search_run_id is not null;

-- ---------------------------------------------------------------------------
-- source_evidence
-- ---------------------------------------------------------------------------
create table public.source_evidence (
  id uuid primary key default gen_random_uuid(),
  conference_id uuid not null references public.conferences (id) on delete cascade,
  organizer_id uuid references public.organizers (id) on delete set null,
  search_run_id uuid references public.search_runs (id) on delete set null,
  source_url text not null,
  source_title text,
  extracted_text_snippet text not null,
  evidence_type text,
  extraction_date timestamptz not null default now()
);

create index idx_source_evidence_conference_id on public.source_evidence (conference_id);
create index idx_source_evidence_organizer_id on public.source_evidence (organizer_id);

-- ---------------------------------------------------------------------------
-- updated_at trigger
-- ---------------------------------------------------------------------------
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger conferences_set_updated_at
  before update on public.conferences
  for each row
  execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- RLS (deny-all until Auth in Phase 7; server uses service role)
-- ---------------------------------------------------------------------------
alter table public.search_runs enable row level security;
alter table public.conferences enable row level security;
alter table public.organizers enable row level security;
alter table public.source_evidence enable row level security;

create policy "deny_all_search_runs" on public.search_runs
  for all using (false);

create policy "deny_all_conferences" on public.conferences
  for all using (false);

create policy "deny_all_organizers" on public.organizers
  for all using (false);

create policy "deny_all_source_evidence" on public.source_evidence
  for all using (false);
