-- Lock down all public tables. No policies are created on purpose:
-- the frontend never talks to these tables directly. Agents and the backend
-- use the service-role key (or the postgres role), which bypasses RLS.
alter table public.system_prompts    enable row level security;
alter table public.opportunity_cards enable row level security;
alter table public.project_board     enable row level security;
alter table public.agent_inbox       enable row level security;
alter table public.agent_run_reports enable row level security;

-- Keep every previous prompt version. DB is the master copy of prompts.
create table if not exists public.system_prompts_history (
  id          bigint generated always as identity primary key,
  prompt_id   bigint not null,
  key         text   not null,
  content     text   not null,
  version     integer,
  archived_at timestamptz not null default timezone('utc', now())
);
alter table public.system_prompts_history enable row level security;

create or replace function public.archive_system_prompt()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.content is distinct from old.content then
    insert into public.system_prompts_history (prompt_id, key, content, version)
    values (old.id, old.key, old.content, old.version);
    new.version    := coalesce(old.version, 0) + 1;
  end if;
  new.updated_at := timezone('utc', now());
  return new;
end;
$$;

create or replace trigger trg_archive_system_prompt
  before update on public.system_prompts
  for each row execute function public.archive_system_prompt();

-- Generic updated_at maintenance (needed for "stuck > 6h" detection).
create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at := timezone('utc', now());
  return new;
end;
$$;

create or replace trigger trg_set_updated_at before update on public.project_board
  for each row execute function public.set_updated_at();

create or replace trigger trg_set_updated_at before update on public.agent_inbox
  for each row execute function public.set_updated_at();

create or replace trigger trg_set_updated_at before update on public.opportunity_cards
  for each row execute function public.set_updated_at();
