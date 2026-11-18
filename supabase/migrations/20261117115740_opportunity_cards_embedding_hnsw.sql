-- IF-24: GET /api/cards/{id}/similar orders by cosine distance on opportunity_cards.embedding.
-- The HNSW index already exists in Supabase; this records it in the repo (no-op there).
create index if not exists opportunity_cards_embedding_idx
  on public.opportunity_cards using hnsw (embedding vector_cosine_ops);
