-- IF-23: one row per ingestion CLI run, per source, so broken adapters and quota
-- problems are visible and the UI can show "last updated" per source.
-- Written by the ingestion pipeline (service role); read by GET /api/stats. Additive only.

create table if not exists public.ingestion_runs (
  id              bigint generated always as identity primary key,
  source_platform text        not null,
  started_at      timestamptz not null default now(),
  finished_at     timestamptz,
  status          text        not null,
  fetched_count   integer     not null default 0,
  inserted_count  integer     not null default 0,
  skipped_count   integer     not null default 0,
  error_summary   text,       -- short human-readable reason; never secrets, keys or full request URLs
  constraint ingestion_runs_source_chk check (source_platform in
    ('reddit','github','hackernews','stackexchange','g2','capterra','other')),
  constraint ingestion_runs_status_chk check (status in ('Success','Partial','Failed')),
  constraint ingestion_runs_counts_chk check (fetched_count >= 0 and inserted_count >= 0 and skipped_count >= 0)
);

comment on column public.ingestion_runs.error_summary is
  'Short failure reason. Must never contain secrets, API keys or request URLs with credentials.';

-- Latest run per source (GET /api/stats).
create index if not exists ingestion_runs_source_started_idx
  on public.ingestion_runs (source_platform, started_at desc);

alter table public.ingestion_runs enable row level security;
