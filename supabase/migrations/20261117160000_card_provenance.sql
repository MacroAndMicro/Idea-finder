-- IF-35: machine-readable provenance and signal spread on opportunity_cards, so the UI can show
-- "12 mentions across 3 sources, last seen 2 days ago" and every card records which prompt/model
-- wrote it. Filled by card synthesis (IF-29). Additive only: all columns nullable, no drops/renames.

alter table public.opportunity_cards
  add column if not exists signal_count   integer,
  add column if not exists platform_count integer,
  add column if not exists first_seen_at  timestamptz,
  add column if not exists last_seen_at   timestamptz,
  add column if not exists llm_model      text,
  add column if not exists prompt_version text;

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'opportunity_cards_spread_counts_chk'
                 and conrelid = 'public.opportunity_cards'::regclass) then
    alter table public.opportunity_cards add constraint opportunity_cards_spread_counts_chk
      check ((signal_count is null or signal_count >= 0) and (platform_count is null or platform_count >= 0));
  end if;
end $$;

comment on column public.opportunity_cards.signal_count   is 'Number of raw signals behind the card (IF-35).';
comment on column public.opportunity_cards.platform_count is 'Number of distinct source platforms among those signals (IF-35).';
comment on column public.opportunity_cards.first_seen_at  is 'Earliest source_created_at among the card''s signals (IF-35).';
comment on column public.opportunity_cards.last_seen_at   is 'Latest source_created_at among the card''s signals (IF-35).';
comment on column public.opportunity_cards.llm_model      is 'LLM model that synthesized the card; internal, not exposed by the API (IF-35).';
comment on column public.opportunity_cards.prompt_version is 'Card synthesis prompt version; internal, not exposed by the API (IF-35).';

-- GET /api/cards?sort=recent orders by last_seen_at desc nulls last.
create index if not exists opportunity_cards_last_seen_idx
  on public.opportunity_cards (last_seen_at desc nulls last, id desc);
