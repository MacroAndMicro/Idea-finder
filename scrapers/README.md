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
  ingest.py          CLI: python -m scrapers.ingest --source {hackernews,github,stackexchange,reddit}
  queries.toml       reviewed default queries / sites / subreddits per source
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

Env vars: `GITHUB_TOKEN`, `GITHUB_DISCUSSION_QUERIES` (optional), `GITHUB_ISSUE_LOOKBACK_DAYS` (optional, default 14), `STACKEXCHANGE_KEY`, `STACKEXCHANGE_LOOKBACK_DAYS` (optional, default 14), `SCRAPER_USER_AGENT` (optional),
`LLM_PROVIDER`/`LLM_MODEL`/`LLM_API_KEY`, `EMBEDDING_PROVIDER`/`EMBEDDING_MODEL`/
`EMBEDDING_API_KEY`/`EMBEDDING_DIMENSIONS` (must be 1536). Adding a source = one new
`SourceAdapter` subclass; G2/Capterra are Phase 2 and intentionally absent.

## Daily run (one command)

Operator runbook (prerequisites, output, failures): [`docs/pipeline-ops.md`](../docs/pipeline-ops.md).

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
stage failed. `--dry-run` = every stage's dry-run: no writes, no LLM/embedding requests (IF-85).

**Backlog (IF-65).** At the end the pipeline prints, read-only, one line per source plus a
`total` line:

```
backlog source=github ingested=50 extracted=8 skipped=0 unprocessed=42 days_to_clear=1 per_day=112
```

`extracted` = has a `signal_extractions` row, `skipped` = processed by the pre-filter with no
row, `unprocessed` = `processed_at` null, `days_to_clear = ceil(unprocessed / --extract-limit)`
(one pipeline run per day). Each source line assumes the whole daily budget; the `total`
line is the shared-budget estimate. Missing Supabase secrets or a failed read print
`backlog skipped: …` and never fail the pipeline.

## Ingest

```
python -m scrapers.ingest --source {github,hackernews,reddit,stackexchange} [--limit 50] [--query Q ...] [--since-days D] [--dry-run]
```

Needs `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` (not for `--dry-run`). Re-runs are safe:
rows already present for `(source_platform, external_id)` are skipped, never overwritten.

**Look-back window (IF-75).** Without `--since-days`, ingest starts from the `started_at` of
the newest `Success` row in `ingestion_runs` for that source, minus a 1-hour overlap
(`SINCE_OVERLAP`), never more than 14 days back. With no such row, in `--dry-run`, or if the
lookup fails, it uses the 14-day default; an explicit `--since-days` always wins. Each run
prints `since=<iso> reason=last_success|default|flag`. GitHub issues and discussions pass the
full UTC instant to search (`created:>=YYYY-MM-DDTHH:MM:SSZ`, IF-83); a date-only filter would
skip the rest of the since day.

### Default queries — `scrapers/queries.toml` (IF-51)

Without `--query`, ingest uses the per-source queries in `scrapers/queries.toml` (read with
stdlib `tomllib`). Each entry has a one-line comment naming the B2B pain it targets, so a
merge request that changes the file is the review record. The file can also hold
`[stackexchange] sites` and `[reddit] subreddits`; `STACKEXCHANGE_SITES` /
`REDDIT_SUBREDDITS` still override them. A test fails if an `ingest.ADAPTERS` source has no
entry, if an unknown source (e.g. `g2`) appears, or if an entry lacks its comment. Keep
it short: every query costs API requests (adapters keep their rate limits and page caps).

### GitHub Issues + Discussions (IF-74)

`--source github` runs two streams on one `HttpClient` (2.5 s spacing, `X-RateLimit-*` /
`Retry-After` handling) and interleaves them so a shared `--limit` reaches both:
- **Issues** — REST `search/issues` with `[github] queries`, `reactions:>=3`, sorted by
  `created` desc, queries interleaved round-robin. **Rolling look-back (IF-93):** the
  `created:>=` window starts at the earlier of the run's `since` and *now − N days*
  (`GITHUB_ISSUE_LOOKBACK_DAYS`, default 14; `0` = plain `since`). A ~4 h `since` window
  alone never saw issues once they had earned 3 reactions; re-seen issues are skipped by the
  store's `(source_platform, external_id)` de-dup. Same page cap (`max_pages`) and 2.5 s
  spacing as before, so no extra requests per run.
- Discussions keep the plain run `since` window (unchanged; they have no reaction threshold).
- **Discussions** — official GraphQL API, `search(type: DISCUSSION)` POSTed to
  `https://api.github.com/graphql` with `GITHUB_TOKEN` (plain HTTPS, no client library), using
  `[github] discussions` from `queries.toml` (override: `GITHUB_DISCUSSION_QUERIES`,
  comma-separated). 50 per page, at most 2 pages per query. Stored as
  `source_platform=github`, `external_id=discussion:<owner>/<repo>#<number>`, tags
  `["discussion", <category>]`. GraphQL `errors` or any HTTP failure stop the discussion
  stream with a warning; issues are never affected. Note: Claude Code cloud sessions block
  GraphQL (HTTP 403), so discussions only arrive when ingest runs elsewhere.

### Stack Exchange (IF-94)

`--source stackexchange` calls `/2.3/search/advanced` with `STACKEXCHANGE_KEY` for every
`[stackexchange] queries` × `sites` pair, interleaved round-robin so one pair cannot fill
`--limit`. **Rolling look-back:** `fromdate` is the earlier of the run's `since` and
*now − N days* (`STACKEXCHANGE_LOOKBACK_DAYS`, default 14; `0` = plain `since`). A ~4 h
window held 0–1 questions per query/site and captured every question at birth (score 0,
no answers). **Signal choice:** `sort=activity` (desc) so questions that later earn answers,
votes or edits resurface inside the window, and questions with a negative score are
dropped client-side (`MIN_SCORE = 0`: the community marked them unclear/off-topic). We do
not require answers — an unanswered "how do I…" is often the strongest pain signal.
Re-seen questions are skipped by the store's `(source_platform, external_id)` de-dup.
Unchanged: `backoff` honored, stop below `QUOTA_FLOOR` (50) `quota_remaining`, 0.5 s
spacing, `max_pages` 3 per pair, no extra sites.

### Reddit

Official OAuth API only, app-only client credentials: token from
`https://www.reddit.com/api/v1/access_token`, all data calls to `https://oauth.reddit.com`
(no www/old.reddit HTML). Needs `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` and
`REDDIT_USER_AGENT` (sent verbatim — Reddit asks for `<platform>:<app id>:<version>
(by /u/<username>)`); if any is missing, `--source reddit` exits 2 naming the variable and
writes nothing. Honors `X-Ratelimit-Remaining` / `X-Ratelimit-Reset` (seconds until reset)
and spaces requests 1 s apart. Submissions only (subreddit search, newest first, stops at
`--since-days`); NSFW, promoted and stickied posts are skipped. Comments are not fetched yet.

Default subreddits (B2B / developer workflow pain; listed in `queries.toml`, override
with `REDDIT_SUBREDDITS`, comma-separated): `sysadmin`, `devops`, `SaaS`, `dataengineering`, `ExperiencedDevs`,
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

### Threshold calibration (IF-63)

```
python -m scrapers.cluster --report [--min-signals 2]
```

Read-only: prints the pairwise similarity histogram of the embedded B2B pain signals and
cluster count / sizes / qualifying clusters at thresholds 0.70–0.90 (step 0.02).

Findings, 2026-11-18 (`gemini/gemini-embedding-2`, 6 embedded B2B pain signals, 15 pairs):
similarity min 0.539 · median 0.629 · max 0.716. At every threshold 0.72–0.90 all 6 are
singletons; at 0.70 one 3-signal cluster forms around the 0.716 pair. On reading them, the
6 signals are 6 different problems (the 0.716 pair is two different complaints about one
agent tool), so the singletons come from unrelated signals, not from a strict threshold.
For this model unrelated-but-same-domain posts already score 0.54–0.72, so the threshold
must stay clearly above ~0.72. **`SIMILARITY_THRESHOLD` stays 0.82**; re-run the report
once there are real same-pain pairs to check the upper side.
`tests/test_cluster_threshold.py` checks the mechanics on a synthetic labelled fixture
(`tests/fixtures/cluster/labelled_pairs.json`, 10 same-pain + 10 different-pain pairs).

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
- Rejections are remembered (IF-48): a cluster answered `valid_opportunity: false` or with
  invalid output is stored in `synthesis_rejections` by fingerprint
  (`sha256(prompt_version + sorted signal ids)`) and skipped with no LLM call
  (`skipped_rejected=` in the summary) until its signal set or the prompt version changes.
- A new card and its `card_signals` links are written in one transaction through the SQL
  function `insert_card_with_links(card jsonb, signal_ids bigint[])` (PostgREST RPC,
  service_role only), so a failed link can never leave a card without evidence.
- A quota-exhausted provider response stops the run at once.
- **Quality gate (IF-62, `card_quality.py`).** Before a new card is embedded or written,
  pure non-LLM checks run on the row: `trigger_counts` (every "N posts / mentions /
  signals / threads / reports / issues / questions" equals the cluster's signal count and
  every "N platforms / sources / sites" its platform count — digits and one…twenty),
  `snippet_in_evidence` (normalised snippet occurs in a member signal's title + body),
  `problem_statement_sentences` (1–2), `economic_intent_enum`, `mvp_wedge_nonempty`,
  `duct_tape_nonempty`, `confidence_range` (integer 1–100). Any failure → no card; the
  cluster is remembered in `synthesis_rejections` with reason `quality:<rule>[,<rule>…]`
  (so it costs no LLM call again until its signals or the prompt change). Each non-dry run
  prints `quality_gate passed=N failed=M <rule>=count …`. The check is fail-closed: a
  phrase like "5 data sources" in the model's text fails `trigger_counts` on purpose.
