-- Test-only mirror of public.opportunity_cards as it exists in Supabase.
-- Why a mirror and not supabase/migrations: the base table predates the migrations folder
-- (migrations only ALTER it), so they cannot build it from an empty database.
-- The embedding column is added only when pgvector is available (it is in CI).
-- Everything lives in the isolated schema if_test (tests set hibernate.default_schema=if_test),
-- so running the tests against a real DATABASE_URL can never touch public tables.
-- Executed as one statement (see @SqlConfig in the tests) because of the DO block.
create schema if not exists if_test;
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
  constraint opportunity_cards_source_chk check (source_platform in
    ('reddit','github','hackernews','stackexchange','g2','capterra','other')),
  constraint opportunity_cards_intent_chk check (economic_intent is null or economic_intent in
    ('High','Medium','Low','Unspecified')),
  constraint opportunity_cards_confidence_chk check (confidence_score is null or confidence_score between 1 and 100)
);
do $$
begin
  if exists (select 1 from pg_available_extensions where name = 'vector') then
    create extension if not exists vector;
    alter table if_test.opportunity_cards add column embedding vector(1536);
  end if;
end $$;
