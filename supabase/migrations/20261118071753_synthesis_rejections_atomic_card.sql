-- IF-48: card synthesis hardening. Additive only (new table + new function).
--
-- 1. synthesis_rejections: clusters the LLM rejected (valid_opportunity = false) or whose
--    output failed validation, keyed by a fingerprint of (prompt_version + sorted signal
--    ids). scrapers.synthesize skips a remembered fingerprint, so the same cluster is not
--    re-sent on every run and cannot starve other clusters of the tiny daily LLM budget.
--    A cluster whose signal set changes gets a new fingerprint and is tried again.
-- 2. insert_card_with_links(card jsonb, signal_ids bigint[]): inserts one opportunity_cards
--    row and its card_signals links in a single transaction (one PostgREST RPC call), so a
--    failed link can no longer leave a card without evidence.

create table if not exists public.synthesis_rejections (
  fingerprint    text        primary key,
  signal_ids     bigint[]    not null,
  prompt_version text        not null,
  reason         text        not null,
  llm_model      text,
  created_at     timestamptz not null default now(),
  constraint synthesis_rejections_reason_chk check (reason in ('rejected', 'invalid'))
);

comment on table public.synthesis_rejections is
  'IF-48: clusters the card-synthesis LLM rejected or answered invalidly; skipped until the signal set or prompt changes.';

alter table public.synthesis_rejections enable row level security;
grant select, insert, update on table public.synthesis_rejections to service_role;

create or replace function public.insert_card_with_links(card jsonb, signal_ids bigint[])
returns bigint
language plpgsql
security invoker
set search_path = ''
as $$
declare
  cols    text;
  unknown text;
  new_id  bigint;
begin
  if card is null or jsonb_typeof(card) <> 'object' then
    raise exception 'card must be a JSON object';
  end if;

  select string_agg(k, ', ') into unknown
  from jsonb_object_keys(card) as k
  where k = 'id' or not exists (
    select 1 from pg_catalog.pg_attribute a
    where a.attrelid = 'public.opportunity_cards'::regclass
      and a.attnum > 0 and not a.attisdropped and a.attname = k);
  if unknown is not null then
    raise exception 'unknown or forbidden card keys: %', unknown;
  end if;

  select string_agg(quote_ident(k), ', ') into cols from jsonb_object_keys(card) as k;
  if cols is null then
    raise exception 'card has no columns';
  end if;

  execute format(
    'insert into public.opportunity_cards (%1$s) '
    'select %1$s from pg_catalog.jsonb_populate_record(null::public.opportunity_cards, $1) '
    'returning id', cols)
    into new_id using card;

  insert into public.card_signals (card_id, signal_id)
  select new_id, s from unnest(coalesce(signal_ids, '{}'::bigint[])) as s
  on conflict do nothing;

  return new_id;
end
$$;

comment on function public.insert_card_with_links(jsonb, bigint[]) is
  'IF-48: atomic opportunity_cards insert + card_signals links; returns the new card id.';

revoke all on function public.insert_card_with_links(jsonb, bigint[]) from public;
revoke all on function public.insert_card_with_links(jsonb, bigint[]) from anon, authenticated;
grant execute on function public.insert_card_with_links(jsonb, bigint[]) to service_role;
