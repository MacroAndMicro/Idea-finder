-- Canonical agent names, statuses and types, enforced by the database
-- so agents cannot drift. Keep in sync with system_prompts.agent_operating_manual.

-- ---------- project_board ----------
alter table public.project_board
  add column if not exists ticket_key          text generated always as ('IF-' || id::text) stored,
  add column if not exists severity            text,
  add column if not exists area                text,
  add column if not exists acceptance_criteria text,
  add column if not exists repro_steps         text,
  add column if not exists effort_days         numeric(4,1),
  add column if not exists pr_link             text;

alter table public.project_board alter column assignee    set default 'Unassigned';
alter table public.project_board alter column assignee    set not null;
alter table public.project_board alter column status      set not null;
alter table public.project_board alter column priority    set not null;
alter table public.project_board alter column needs_founder set not null;

alter table public.project_board
  add constraint project_board_status_chk check (status in
    ('Backlog','To Do','In Progress','Ready for QA','Deployed','Closed','Not needed')),
  add constraint project_board_type_chk check (type in
    ('Bug','Data Error','Feature','UI Component','UI Polish','Data Pipeline','Design','Chore')),
  add constraint project_board_priority_chk check (priority in ('Critical','High','Medium','Low')),
  add constraint project_board_severity_chk check (severity is null or severity in ('Critical','High','Medium','Low')),
  add constraint project_board_area_chk check (area is null or area in
    ('Frontend','Backend API','Scraping Pipeline','LLM Pipeline','Database','Auth/Billing','Infra/CI')),
  add constraint project_board_assignee_chk check (assignee in
    ('Unassigned','Founder','PM Agent','QA Agent','Senior SWE','Dev Intern','Senior Designer','Data Engineer','User Simulator')),
  add constraint project_board_reported_by_chk check (reported_by is null or reported_by in
    ('Founder','PM Agent','QA Agent','Senior SWE','Dev Intern','Senior Designer','Data Engineer','User Simulator')),
  add constraint project_board_effort_chk check (effort_days is null or effort_days > 0);

create unique index if not exists project_board_ticket_key_idx on public.project_board (ticket_key);
create index if not exists project_board_queue_idx on public.project_board (status, assignee, priority);

-- ---------- agent_inbox ----------
-- agent  = recipient ('Founder' for questions to the founder, 'All agents' for broadcasts)
-- sender = author
alter table public.agent_inbox
  add column if not exists ticket_id bigint references public.project_board(id) on delete set null;
alter table public.agent_inbox alter column status set not null;

alter table public.agent_inbox
  add constraint agent_inbox_agent_chk check (agent in
    ('Founder','All agents','PM Agent','QA Agent','Senior SWE','Dev Intern','Senior Designer','Data Engineer','User Simulator')),
  add constraint agent_inbox_sender_chk check (sender in
    ('Founder','PM Agent','QA Agent','Senior SWE','Dev Intern','Senior Designer','Data Engineer','User Simulator')),
  add constraint agent_inbox_status_chk check (status in ('Open','Answered','Handled','Closed'));

create index if not exists agent_inbox_agent_status_idx on public.agent_inbox (agent, status);
create index if not exists agent_inbox_sender_status_idx on public.agent_inbox (sender, status);

-- ---------- agent_run_reports ----------
alter table public.agent_run_reports
  add column if not exists run_status      text not null default 'Success',
  add column if not exists founder_actions text;

alter table public.agent_run_reports
  add constraint agent_run_reports_agent_chk check (agent in
    ('PM Agent','QA Agent','Senior SWE','Dev Intern','Senior Designer','Data Engineer','User Simulator')),
  add constraint agent_run_reports_status_chk check (run_status in ('Success','Partial','Failed','Skipped'));

create index if not exists agent_run_reports_agent_created_idx on public.agent_run_reports (agent, created_at desc);

-- ---------- opportunity_cards ----------
-- Embedding model is not chosen yet; record which model produced each vector.
alter table public.opportunity_cards
  add column if not exists title           text,
  add column if not exists embedding_model text;

alter table public.opportunity_cards
  add constraint opportunity_cards_source_chk check (source_platform in
    ('reddit','github','g2','capterra','other')),
  add constraint opportunity_cards_intent_chk check (economic_intent is null or economic_intent in
    ('High','Medium','Low','Unspecified')),
  add constraint opportunity_cards_confidence_chk check (confidence_score is null or confidence_score between 1 and 100);

create index if not exists opportunity_cards_embedding_idx
  on public.opportunity_cards using hnsw (embedding vector_cosine_ops);

-- ---------- test_personas (User Simulator cast) ----------
create table if not exists public.test_personas (
  id                  bigint generated always as identity primary key,
  persona_name        text not null unique,
  tier                text not null check (tier in ('Free','Pro','Enterprise')),
  description         text not null,
  credentials_env_var text,   -- NAME of the env var holding credentials, never the secret itself
  active              boolean not null default true,
  notes               text,
  created_at          timestamptz not null default timezone('utc', now()),
  updated_at          timestamptz not null default timezone('utc', now())
);
alter table public.test_personas enable row level security;

create or replace trigger trg_set_updated_at before update on public.test_personas
  for each row execute function public.set_updated_at();
