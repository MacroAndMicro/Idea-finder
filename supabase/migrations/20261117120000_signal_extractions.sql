-- IF-22: per-signal LLM extraction results + per-signal embeddings, so the
-- Data Engineer can extract and cluster raw_signals before building cards.
-- Additive only. The pgvector extension already exists (opportunity_cards.embedding).

create table if not exists public.signal_extractions (
  id               bigint generated always as identity primary key,
  signal_id        bigint      not null
                   references public.raw_signals (id) on delete cascade,
  is_pain_point    boolean,
  is_b2b           boolean,
  problem_summary  text,
  duct_tape        text,
  economic_intent  text,
  persona          text,
  workflow_tags    text[],
  llm_provider     text,
  llm_model        text,
  prompt_version   text,
  extracted_at     timestamptz not null default now(),
  constraint signal_extractions_signal_uq unique (signal_id),
  -- Same values as opportunity_cards.economic_intent.
  constraint signal_extractions_intent_chk check (economic_intent is null or economic_intent in
    ('High','Medium','Low','Unspecified'))
);

alter table public.signal_extractions enable row level security;

alter table public.raw_signals add column if not exists embedding vector(1536);
alter table public.raw_signals add column if not exists embedding_model text;

create index if not exists raw_signals_embedding_idx
  on public.raw_signals using hnsw (embedding vector_cosine_ops);
