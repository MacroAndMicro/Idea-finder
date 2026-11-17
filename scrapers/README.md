# scrapers — ingestion adapters + LLM pipeline

Python 3.12, standard library only at runtime. Phase 1 sources via **official APIs only**
(no HTML scraping, no user-agent spoofing, no anti-bot evasion).

```
scrapers/
  config.py          env-only config; MissingSecretError names the variable, never its value
  models.py          RawSignal (mirrors public.raw_signals) + hashing helpers
  http_client.py     shared HttpClient: timeout, exponential backoff, Retry-After,
                     X-RateLimit-* waits, gzip, honest User-Agent (SCRAPER_USER_AGENT)
  adapters/          SourceAdapter base + hackernews, github, stackexchange
  store.py           SupabaseStore: idempotent insert into raw_signals (+ ingestion_runs if present)
  cluster.py         pure clustering of pain-point signals + 1–100 confidence score
  ingest.py          CLI: python -m scrapers.ingest --source {hackernews,github,stackexchange}
  llm/               provider-agnostic LLMClient / EmbeddingClient: base, factory, fake, gemini
  tests/             pytest suite (test_*.py, conftest.py, helpers.py)
  tests/fixtures/    recorded API responses (github, hackernews, stackexchange) — tests never touch the network
```

Run: `pip install -r scrapers/requirements.txt && ruff check scrapers && pytest scrapers`

Env vars: `GITHUB_TOKEN`, `STACKEXCHANGE_KEY`, `SCRAPER_USER_AGENT` (optional),
`LLM_PROVIDER`/`LLM_MODEL`/`LLM_API_KEY`, `EMBEDDING_PROVIDER`/`EMBEDDING_MODEL`/
`EMBEDDING_API_KEY`/`EMBEDDING_DIMENSIONS` (must be 1536). Adding a source = one new
`SourceAdapter` subclass; G2/Capterra are Phase 2 and intentionally absent.

## Ingest

```
python -m scrapers.ingest --source hackernews [--limit 50] [--query Q ...] [--since-days 14] [--dry-run]
```

Needs `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` (not for `--dry-run`). Re-runs are safe:
rows already present for `(source_platform, external_id)` are skipped, never overwritten.

## Clustering & confidence (`cluster.py`)

Only signals with `is_pain_point` and `is_b2b` are clustered. Greedy centroid clustering on
cosine similarity, processed in ascending `signal_id` order (deterministic): a signal joins the
most similar existing cluster centroid if similarity >= `SIMILARITY_THRESHOLD` (**0.82**,
overridable per call), else starts a new cluster; ties go to the older cluster.
Vectors must be 1536-d.

Confidence score (rounded, clamped to 1–100; weights sum to 100):

| Factor | Weight | Formula |
|---|---|---|
| Volume | 30 | `min(1, log2(1+n) / log2(11))` — saturates at 10 signals |
| Source spread | 25 | `min(1, (distinct_platforms - 1) / 2)` — saturates at 3 platforms |
| Recency | 20 | share of signals created within 30 days of `now` (unknown date = not recent) |
| Engagement | 15 | `min(1, log10(1+Σ(score+comments)) / log10(501))` |
| Economic intent | 10 | max over signals: High 1 · Medium 0.6 · Low 0.3 · Unspecified 0 |
