# scrapers — ingestion adapters + LLM pipeline

Python 3.12, standard library only at runtime. Phase 1 sources via **official APIs only**
(no HTML scraping, no user-agent spoofing, no anti-bot evasion).

```
scrapers/
  config.py          env-only config; MissingSecretError names the variable, never its value
  models.py          RawSignal (mirrors public.raw_signals) + hashing helpers
  http_client.py     shared HttpClient: timeout, exponential backoff, Retry-After,
                     X-RateLimit-* waits, gzip, honest User-Agent (SCRAPER_USER_AGENT)
  adapters/          SourceAdapter base + hackernews, github, stackexchange, reddit
  store.py           SupabaseStore: idempotent insert into raw_signals (+ ingestion_runs if present)
  prioritize.py      deterministic ranking + skip rule for which signals extract spends LLM requests on
  cluster.py         pure clustering of pain-point signals + 1–100 confidence score
  ingest.py          CLI: python -m scrapers.ingest --source {hackernews,github,stackexchange}
  embed.py           CLI: python -m scrapers.embed — 1536-d embeddings on raw_signals
  extract.py         CLI: python -m scrapers.extract — per-signal LLM extraction → signal_extractions
  synthesize.py      CLI: python -m scrapers.synthesize — clusters → opportunity_cards + card_signals
  pipeline.py        CLI: python -m scrapers.pipeline — ingest → extract → embed → synthesize
  llm/               provider-agnostic LLMClient / EmbeddingClient: base, factory, fake, gemini
  llm/prompts/       versioned prompts (extract_signal_v1, extract_signal_batch_v1, synthesize_card_v1); never edited after shipping
  llm/extraction_schema.py  strict JSON validation of extraction output
  llm/card_schema.py        strict JSON validation of card-synthesis output
  tests/             pytest suite (test_*.py, conftest.py, helpers.py)
  tests/fixtures/    recorded API responses (github, hackernews, stackexchange, reddit, gemini) — tests never touch the network
```

Run: `pip install -r scrapers/requirements.txt && ruff check scrapers && pytest scrapers`

Env vars: `GITHUB_TOKEN`, `STACKEXCHANGE_KEY`, `SCRAPER_USER_AGENT` (optional),
`LLM_PROVIDER`/`LLM_MODEL`/`LLM_API_KEY`, `EMBEDDING_PROVIDER`/`EMBEDDING_MODEL`/
`EMBEDDING_API_KEY`/`EMBEDDING_DIMENSIONS` (must be 1536). Adding a source = one new
`SourceAdapter` subclass; G2/Capterra are Phase 2 and intentionally absent.

## Daily run (one command)

```
python -m scrapers.pipeline [--sources hackernews,github,stackexchange,reddit]
    [--extract-limit 112] [--extract-batch-size 8] [--extract-max-requests 18]
    [--synthesize-limit 2] [--skip-synthesize] [--dry-run]
```

Runs `ingest` per source, then `extract` (capped), `embed`, `synthesize` (capped), reusing
each module's `run()`. Defaults fit the Gemini free tier (20 generate requests/day):

| Stage | Requests/day | Signals |
|---|---|---|
| extract batches (8 signals each) | 14 | 112 |
| extract single-signal retries (missing/invalid batch items) | ≤ 4 | — |
| synthesize card writes | 2 | — |
| **Total** | **≤ 20** | up to 112 classified/day (was 18) |

`--extract-max-requests 18` is a hard cap, so retries can never eat the synthesize budget;
signals not reached wait for the next run. Embed runs after extract because it embeds only signals
already classified as B2B pain. Sources with missing secrets (e.g. `REDDIT_*`) are skipped
with a note; a failing source or stage is reported and the rest still run. Prints one
`stage=… status=…` line per stage plus a `pipeline status=…` total; exit 0 only if no
stage failed. `--dry-run` = ingest/embed/synthesize dry-runs, extract skipped.

## Ingest

```
python -m scrapers.ingest --source {github,hackernews,reddit,stackexchange} [--limit 50] [--query Q ...] [--since-days 14] [--dry-run]
```

Needs `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` (not for `--dry-run`). Re-runs are safe:
rows already present for `(source_platform, external_id)` are skipped, never overwritten.

### Reddit

Official OAuth API only, app-only client credentials: token from
`https://www.reddit.com/api/v1/access_token`, all data calls to `https://oauth.reddit.com`
(no www/old.reddit HTML). Needs `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` and
`REDDIT_USER_AGENT` (sent verbatim — Reddit asks for `<platform>:<app id>:<version>
(by /u/<username>)`); if any is missing, `--source reddit` exits 2 naming the variable and
writes nothing. Honors `X-Ratelimit-Remaining` / `X-Ratelimit-Reset` (seconds until reset)
and spaces requests 1 s apart. Submissions only (subreddit search, newest first, stops at
`--since-days`); NSFW, promoted and stickied posts are skipped. Comments are not fetched yet.

Default subreddits (B2B / developer workflow pain; override with `REDDIT_SUBREDDITS`,
comma-separated): `sysadmin`, `devops`, `SaaS`, `dataengineering`, `ExperiencedDevs`,
`msp`, `salesforce`, `analytics`.

## Extract (per-signal LLM)

```
python -m scrapers.extract [--limit 40] [--batch-size 8] [--max-requests N] [--dry-run]
```

Takes `raw_signals` with `processed_at` null, ranked best-first by `prioritize.py` (see
below), and sends the top `--limit` in batches of
`--batch-size` (default 8, max 15) with prompt `extract_signal_batch_v1` through the
`LLM_*`-selected client: one request classifies the whole batch (IF-49). The model returns
a JSON array keyed by signal `id`; every item is validated on its own
(`llm/extraction_schema.py`) and upserted into `signal_extractions` with `llm_provider`,
`llm_model` and the `prompt_version` that produced it, then `processed_at` is set.
- Unknown / duplicate ids in the reply are ignored. A missing or invalid item is retried
  once **alone** with `extract_signal_v1`; still invalid → stored as a failed row
  (`is_pain_point`/`is_b2b` null, never clustered) and marked processed. Valid items of
  the same batch are always saved.
- `--batch-size 1` = the original per-signal mode (`extract_signal_v1`, one retry).
- `--max-requests` caps LLM requests per run; signals not reached stay unprocessed.
- Per-signal text in a batch is truncated to 300/3000 chars (title/body).
- Provider/network errors leave the signal(s) unprocessed; 3 in a row stop the run. A
  quota-exhausted response stops the run at once (results already validated are kept).
- Post text is untrusted: each post fenced in its own `<signal id="…">` tag, any
  `<signal…>`/`</signal>` look-alike in the text neutralised, title/body truncated; the system prompt forbids following it and
  forbids inventing facts (null / `Unspecified` when absent).

### Which signals get the LLM budget (`prioritize.py`, IF-50)

Cheap, deterministic, no LLM, no new dependencies. Nothing is ever deleted from `raw_signals`.

- **Skip rule:** stripped `title` + `body` shorter than `MIN_TEXT_CHARS` (40) → marked
  processed (`processed_at` set) with **no** `signal_extractions` row, so it never uses a
  request. "Processed without an extraction row" = skipped by the pre-filter. The count is
  printed as `skipped=` in the extract summary (dry-run marks nothing).
- **Priority score** (higher first, ties by lower id):

| Term | Formula |
|---|---|
| Engagement | `2.0 × log10(1 + score + 2 × comments)` (negatives → 0) |
| Body length | `2.0 × min(1, len(body) / 1500)` |
| Pain phrases | `1.5 ×` distinct hits in title/body (`workaround`, `broken`, `how do i`, `is there a tool`, `manually`, `we pay`, …), max 4 |
| B2B terms | `1.0 ×` distinct word/tag hits (`team`, `production`, `api`, `integration`, `invoice`, `devops`, …), max 3 |

## Embed (raw_signals)

```
python -m scrapers.embed [--limit 100] [--all] [--dry-run]
```

Embeds `title + body` (truncated to 8000 chars) for `raw_signals` with a null
`embedding`, in batches of 32, via the `EMBEDDING_*`-selected client; writes
`embedding` (exactly 1536 dims, else rejected) and `embedding_model`.
**Choice:** by default only signals whose extraction is `is_pain_point` and `is_b2b`
(the only ones clustering uses), so run `scrapers.extract` first; `--all` embeds
every signal regardless.

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

## Synthesize (clusters → Opportunity Cards)

```
python -m scrapers.synthesize [--min-signals 2] [--limit 10] [--threshold 0.82] [--dry-run]
```

Clusters embedded B2B pain-point signals (`cluster.py`) and writes one `opportunity_cards`
row per cluster with >= `--min-signals` signals (default 2: a card needs corroboration),
plus `card_signals` links. Highest-confidence clusters first; `--limit` caps LLM calls
per run (free-tier quotas) and the rest wait for the next run. `--dry-run` = no LLM, no writes.

- The LLM (prompt `synthesize_card_v1`, schema `llm/card_schema.py`, one retry) writes only
  `title`, `problem_statement`, the "when" sentence of `trigger_context`, `market_size`,
  `duct_tape_solutions`, `mvp_wedge`, and `valid_opportunity` (false → no card).
- Computed in code, never by the model: the `Frequency:` sentence of `trigger_context`
  (post count, platforms, date range), `economic_intent` (strongest intent in the cluster's
  extractions), `confidence_score`, `signal_count`, `platform_count`, `first/last_seen_at`,
  `source_platform` (dominant), `source_url` + `raw_content_snippet` (strongest signal by
  score + comments).
- Idempotent: a cluster with >= 50 % (`OVERLAP_MATCH`) of its signals already linked to a
  card is that card — new signals are linked and counts/confidence/frequency refreshed,
  with no LLM call. A new card whose text embedding has cosine >= **0.90**
  (`CARD_DUPLICATE_THRESHOLD`) with an existing card is merged into it instead.
- A quota-exhausted provider response stops the run at once.
