-- IF-40: baseline for the five base tables that were created in Supabase before
-- supabase/migrations existed. Every later migration only ALTERs them, so without this
-- file the folder cannot build an empty database (new env, Supabase branch, DR, tests).
--
-- Matches the prod DDL as of 2026-11-18 MINUS what later migrations add themselves
-- (they use plain ADD CONSTRAINT, so repeating it here would break the replay):
--   20261116000001: RLS, system_prompts_history, set_updated_at/archive triggers
--   20261116000002: project_board ticket_key/severity/area/acceptance_criteria/repro_steps/
--                   effort_days/pr_link + all CHECKs; agent_inbox ticket_id + CHECKs;
--                   agent_run_reports run_status/founder_actions + CHECKs;
--                   opportunity_cards title/embedding_model + CHECKs + HNSW index
--   20261117160000: opportunity_cards provenance columns
--
-- Idempotent: only CREATE ... IF NOT EXISTS. On prod (where everything exists) it is a no-op.
-- Additive only, no data changes.

create extension if not exists vector with schema public;

create table if not exists public.system_prompts (
  id         bigserial primary key,
  key        text not null unique,
  content    text not null,
  version    integer default 1,
  updated_at timestamptz default timezone('utc', now())
);

create table if not exists public.opportunity_cards (
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
  embedding           vector(1536)
);

create index if not exists idx_opportunity_cards_confidence
  on public.opportunity_cards (confidence_score desc);
create index if not exists idx_opportunity_cards_platform
  on public.opportunity_cards (source_platform);

create table if not exists public.project_board (
  id            bigserial primary key,
  title         text not null,
  description   text,
  type          text not null,
  status        text not null default 'Backlog',
  priority      text not null default 'Medium',
  assignee      text default 'Unassigned',
  reported_by   text,
  target_week   text,
  needs_founder boolean default false,
  notes         text,
  created_at    timestamptz not null default timezone('utc', now()),
  updated_at    timestamptz not null default timezone('utc', now())
);

create index if not exists idx_project_board_status_assignee
  on public.project_board (status, assignee);

create table if not exists public.agent_inbox (
  id         bigserial primary key,
  agent      text not null,
  sender     text not null,
  question   text not null,
  answer     text,
  status     text default 'Open',
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create index if not exists idx_agent_inbox_agent_status
  on public.agent_inbox (agent, status);

create table if not exists public.agent_run_reports (
  id            bigserial primary key,
  agent         text not null,
  run_summary   text not null,
  metrics_json  jsonb,
  needs_founder boolean default false,
  created_at    timestamptz not null default timezone('utc', now())
);

create index if not exists idx_agent_run_reports_agent
  on public.agent_run_reports (agent, created_at desc);
