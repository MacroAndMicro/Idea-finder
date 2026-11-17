-- IF-2: raw_signals — normalized raw items from ingestion adapters, before LLM
-- extraction turns them into opportunity_cards. Additive only.

create table if not exists public.raw_signals (
  id                 bigint generated always as identity primary key,
  source_platform    text        not null,
  external_id        text        not null,
  url                text        not null,
  title              text,
  body               text,
  author_handle_hash text,       -- hash of the author handle; never store raw usernames
  score              integer,
  comment_count      integer,
  tags               text[],
  source_created_at  timestamptz,
  fetched_at         timestamptz not null default now(),
  processed_at       timestamptz,
  content_hash       text,
  constraint raw_signals_source_chk check (source_platform in
    ('reddit','github','hackernews','stackexchange','g2','capterra','other')),
  constraint raw_signals_source_external_uq unique (source_platform, external_id)
);

comment on column public.raw_signals.author_handle_hash is
  'One-way hash of the source author handle. Raw usernames must never be stored.';

-- Work queue for the LLM extraction step: unprocessed signals only.
create index if not exists raw_signals_unprocessed_idx
  on public.raw_signals (fetched_at)
  where processed_at is null;

alter table public.raw_signals enable row level security;

-- A card can cite many signals; a signal can support many cards.
create table if not exists public.card_signals (
  card_id   bigint not null references public.opportunity_cards (id) on delete cascade,
  signal_id bigint not null references public.raw_signals (id)       on delete cascade,
  primary key (card_id, signal_id)
);

-- Reverse lookup (signal -> cards); the PK already covers card -> signals.
create index if not exists card_signals_signal_idx on public.card_signals (signal_id);

alter table public.card_signals enable row level security;
