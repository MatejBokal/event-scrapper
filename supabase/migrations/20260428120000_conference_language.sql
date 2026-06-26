-- Store detected conference language from LLM extraction (export / display)

alter table public.conferences
  add column if not exists language text;
