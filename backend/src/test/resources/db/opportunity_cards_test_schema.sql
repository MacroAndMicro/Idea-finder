-- Test-only mirror of public.opportunity_cards as it exists in Supabase.
-- Why a mirror and not supabase/migrations: the base table predates the migrations folder
-- (migrations only ALTER it), so they cannot build it from an empty database.
-- The embedding column is added only when pgvector is available (it is in CI).
-- Everything lives in the isolated schema if_test (tests set hibernate.default_schema=if_test),
-- so running the tests against a real DATABASE_URL can never touch public tables.
-- Executed as one statement (see @SqlConfig in the tests) because of the DO block.
create schema if not exists if_test;
drop table if exists if_test.ingestion_runs cascade;
drop table if exists if_test.card_signals cascade;
drop table if exists if_test.raw_signals cascade;
drop table if exists if_test.opportunity_cards cascade;
create table if_test.opportunity_cards (
  id                  bigserial primary key,
  source_platform     text not null,
  source_url          text,
  raw_content_snippet text,
  problem_statement   text not null,
  trigger_context     text not null,
  market_size         text,
  duct_tape_solutions text,
  economic_intent     text,
  mvp_wedge           text,
  confidence_score    numeric,
  status              text default 'Backlog',
  is_b2b_filtered     boolean default true,
  created_at          timestamptz not null default timezone('utc', now()),
  updated_at          timestamptz not null default timezone('utc', now()),
  title               text,
  embedding_model     text,
  -- Mirror of supabase/migrations/20261117160000_card_provenance.sql (IF-35).
  signal_count        integer,
  platform_count      integer,
  first_seen_at       timestamptz,
  last_seen_at        timestamptz,
  llm_model           text,
  prompt_version      text,
  constraint opportunity_cards_spread_counts_chk check ((signal_count is null or signal_count >= 0)
    and (platform_count is null or platform_count >= 0)),
  constraint opportunity_cards_source_chk check (source_platform in
    ('reddit','github','hackernews','stackexchange','g2','capterra','other')),
  constraint opportunity_cards_intent_chk check (economic_intent is null or economic_intent in
    ('High','Medium','Low','Unspecified')),
  constraint opportunity_cards_confidence_chk check (confidence_score is null or confidence_score between 1 and 100)
);
-- Mirror of supabase/migrations/20261117030000_raw_signals.sql.
create table if_test.raw_signals (
  id                 bigint generated always as identity primary key,
  source_platform    text        not null,
  external_id        text        not null,
  url                text        not null,
  title              text,
  body               text,
  author_handle_hash text,
  score              integer,
  comment_count      integer,
  tags               text[],
  source_created_at  timestamptz,
  fetched_at         timestamptz not null default now(),
  processed_at       timestamptz,
  content_hash       text,
  embedding_model    text,
  constraint raw_signals_source_chk check (source_platform in
    ('reddit','github','hackernews','stackexchange','g2','capterra','other')),
  constraint raw_signals_source_external_uq unique (source_platform, external_id)
);
create table if_test.card_signals (
  card_id   bigint not null references if_test.opportunity_cards (id) on delete cascade,
  signal_id bigint not null references if_test.raw_signals (id)       on delete cascade,
  primary key (card_id, signal_id)
);
-- Mirror of supabase/migrations/20261117120100_ingestion_runs.sql (IF-23).
create table if_test.ingestion_runs (
  id              bigint generated always as identity primary key,
  source_platform text        not null,
  started_at      timestamptz not null default now(),
  finished_at     timestamptz,
  status          text        not null,
  fetched_count   integer     not null default 0,
  inserted_count  integer     not null default 0,
  skipped_count   integer     not null default 0,
  error_summary   text,
  constraint ingestion_runs_source_chk check (source_platform in
    ('reddit','github','hackernews','stackexchange','g2','capterra','other')),
  constraint ingestion_runs_status_chk check (status in ('Success','Partial','Failed')),
  constraint ingestion_runs_counts_chk check (fetched_count >= 0 and inserted_count >= 0 and skipped_count >= 0)
);
do $$
begin
  if exists (select 1 from pg_available_extensions where name = 'vector') then
    create extension if not exists vector;
    alter table if_test.opportunity_cards add column embedding vector(1536);
    -- Mirror of supabase/migrations/20261117120000_signal_extractions.sql (IF-22).
    alter table if_test.raw_signals add column embedding vector(1536);
  end if;
end $$;
