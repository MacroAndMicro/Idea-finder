# scrapers — ingestion adapters + LLM pipeline

Python 3.12, standard library only at runtime. Phase 1 sources via **official APIs only**
(no HTML scraping, no user-agent spoofing, no anti-bot evasion).

```
scrapers/
  config.py          env-only config; MissingSecretError names the variable, never its value
  models.py          RawSignal (mirrors public.raw_signals) + hashing helpers
  http.py            shared HttpClient: timeout, exponential backoff, Retry-After,
                     X-RateLimit-* waits, gzip, honest User-Agent (SCRAPER_USER_AGENT)
  adapters/          SourceAdapter base + hackernews, github, stackexchange
  store.py           SupabaseStore: idempotent insert into raw_signals (+ ingestion_runs if present)
  ingest.py          CLI: python -m scrapers.ingest --source {hackernews,github,stackexchange}
  llm/               provider-agnostic LLMClient / EmbeddingClient (fake, gemini)
  tests/fixtures/    recorded API responses — tests never touch the network
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
