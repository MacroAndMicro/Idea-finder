# Pipeline runbook

How to run the daily ingestion + LLM pipeline, read its output, and react when a stage
fails. Details of each stage live in [`scrapers/README.md`](../scrapers/README.md).

## 1. Prerequisites

- Python 3.12, from the repo root: `pip install -r scrapers/requirements.txt`
- Environment variables (names only; see [`.env.example`](../.env.example), never commit values):

| Needed by | Variables |
|---|---|
| Storage (every non-dry stage, backlog report) | `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` |
| extract + synthesize | `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY` |
| embed + synthesize | `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, `EMBEDDING_API_KEY`, `EMBEDDING_DIMENSIONS` (must be `1536`) |
| ingest `github` | `GITHUB_TOKEN` |
| ingest `stackexchange` | `STACKEXCHANGE_KEY` |
| ingest `reddit` | `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT` |
| ingest `hackernews` | none |
| Optional overrides | `SCRAPER_USER_AGENT`, `REDDIT_SUBREDDITS`, `STACKEXCHANGE_SITES`, `GITHUB_DISCUSSION_QUERIES` |

A source whose secrets are missing is skipped, not failed (see §4).

## 2. The daily command

Run once a day, from the repo root:

```bash
python -m scrapers.pipeline
```

It runs `ingest` for every source → `extract` → `embed` → `synthesize`, then prints the
backlog. Useful variants:

```bash
python -m scrapers.pipeline --dry-run                       # no writes, extract skipped; smoke test
python -m scrapers.pipeline --sources hackernews,github     # subset of sources
python -m scrapers.pipeline --skip-synthesize               # ingest + extract + embed only
python -m scrapers.pipeline --help                          # all flags
```

Each stage can also be run alone (all accept `--help`; all but `cluster` accept `--dry-run`):

```bash
python -m scrapers.ingest --source hackernews --dry-run
python -m scrapers.extract --help          # see warning below before using --dry-run
python -m scrapers.embed --dry-run
python -m scrapers.synthesize --dry-run
python -m scrapers.cluster --report        # read-only similarity report
```

> **Warning:** `scrapers.extract --dry-run` still **calls the LLM** (it only skips writes),
> so it spends the daily quota. Use `python -m scrapers.pipeline --dry-run` (which skips
> extract) for a smoke test, or pass `--limit` / `--max-requests` to cap it. Likewise
> `embed --dry-run` (also run by `pipeline --dry-run`) calls the embedding provider for any
> pending signals; `synthesize --dry-run` makes no LLM calls.

## 3. Daily LLM budget

Defaults fit a free tier of 20 generate requests/day. Don't raise them without checking the
provider's quota.

| Stage | Flag (default) | Requests/day |
|---|---|---|
| extract batches (8 signals each) | `--extract-limit 112`, `--extract-batch-size 8` | 14 |
| extract single-signal retries | — | ≤ 4 |
| extract hard cap (batches + retries) | `--extract-max-requests 18` | 18 |
| synthesize card writes | `--synthesize-limit 2` | 2 |
| **Total** | | **≤ 20** |

Signals not reached today stay unprocessed and are picked up by the next run.

## 4. Reading the output

One `stage=` line per stage, a `backlog` block, and one `pipeline` line:

```
stage=ingest:hackernews status=ok exit=0
stage=ingest:reddit status=skipped missing REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT
stage=extract status=ok exit=0
stage=embed status=ok exit=0
stage=synthesize status=ok exit=0
backlog source=github ingested=50 extracted=8 skipped=0 unprocessed=42 days_to_clear=1 per_day=112
pipeline status=success stages=6 ok=5 failed=0 skipped=1
```

| Line | Meaning |
|---|---|
| `status=ok exit=0` | Stage finished cleanly. |
| `status=skipped <reason>` | Not run on purpose: missing source secrets, `--dry-run` (extract), or `--skip-synthesize`. Never fails the pipeline. |
| `status=failed exit=N` | Stage returned non-zero; its own `error:` line just above says why. Later stages still run. |
| `since=<iso> reason=…` | Ingest look-back start: `last_success` (newest successful run − 1 h), `default` (14 days), or `flag` (`--since-days`). |
| `source=… fetched= inserted= skipped=` | Ingest totals; `skipped` = already stored (re-runs are safe). |
| `extract … requests= processed= failed= provider_errors=` | LLM calls used, signals classified, invalid outputs stored as failed rows, provider errors. |
| `synthesize … created= merged= rejected= deferred= errors=` | Cards written / merged into existing ones / rejected by the model / waiting for the next run. |
| `quality_gate passed=N failed=M <rule>=count …` | Non-LLM card checks; failures are not written (see §5). |
| `backlog source=… unprocessed= days_to_clear=` | Signals still waiting for extract and how many daily runs it takes to clear them (`never` = budget is 0). The `total` line is the shared-budget estimate. |
| `backlog skipped: …` | Supabase secrets missing or read failed; informational only. |
| `pipeline status=success\|failed …` | Exit code 0 only if no stage failed. |

## 5. Common failures and what to do

| Symptom | Cause | Action |
|---|---|---|
| `error: Required environment variable X is not set` then `status=failed exit=2` | Missing secret for a stage that needs it | Set `X` in the environment (never in git). If you can't, report it by name and ask the founder. |
| `stage=ingest:<source> status=skipped missing …` | Source secrets not set (e.g. Reddit approval pending) | Expected until keys exist; nothing to do. |
| `error: LLM quota exhausted (HTTP 429); stopping` (extract) or `LLM/embedding quota exhausted` (synthesize) | Daily provider quota used up | Do not re-run today. Results already validated are kept; the rest waits for tomorrow's run. |
| `note: --max-requests N reached` | Extract hit its own cap | Normal; remaining signals carry over. |
| `error: stopping after repeated provider errors` | 3 provider errors in a row (outage, bad key/model) | Check `LLM_MODEL` / `LLM_API_KEY` and the provider's status; re-run later. |
| `quality_gate … failed=M trigger_counts=…` (or other rule) | Model text failed a card check (wrong counts, snippet not in evidence, …) | No action per run: the cluster is remembered in `synthesis_rejections` and costs no LLM call again until its signals or the prompt change. A rule failing every day is worth a ticket. |
| `error: could not read …` / `could not store … (HTTP 5xx)` | Supabase unavailable or key wrong | Check `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY`; re-run — every stage is idempotent. |
| `error: … dimension` (embed/synthesize) | Embedding model doesn't return 1536 dims | Fix `EMBEDDING_MODEL` / `EMBEDDING_DIMENSIONS`; never store other sizes. |
| GitHub discussions warning, issues still ingested | GraphQL blocked (e.g. Claude Code cloud sessions return 403) | Expected in that environment; run elsewhere for discussions. |

Every stage is safe to re-run: ingest skips rows it already has, extract only takes
unprocessed signals, embed only fills null embeddings, and synthesize matches existing cards.
