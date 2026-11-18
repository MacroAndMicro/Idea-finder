# Backend API reference

Read-only JSON API served by `backend/` (Spring Boot). Every endpoint below is a public `GET`;
there is no authentication yet (auth and tier gating are planned features). Taken from the
controllers and services on `main` — when code and this page disagree, the code wins and this
page needs a fix.

| Endpoint | Purpose |
|---|---|
| [`GET /api/health`](#get-apihealth) | Liveness + database check |
| [`GET /api/stats`](#get-apistats) | Ingestion / pipeline counts |
| [`GET /api/ingestion-runs`](#get-apiingestion-runs) | Ingestion run history |
| [`GET /api/cards`](#get-apicards) | Opportunity Card list (filter, search, sort, page) |
| [`GET /api/cards/facets`](#get-apicardsfacets) | Counts per filter option for the card list |
| [`GET /api/cards/{id}`](#get-apicardsid) | One Opportunity Card |
| [`GET /api/cards/{id}/similar`](#get-apicardsidsimilar) | Nearest cards by embedding |
| [`GET /api/cards/{id}/signals`](#get-apicardsidsignals) | Raw signals (evidence) behind a card |

## Conventions (all endpoints)

- **JSON keys** are `snake_case`. Timestamps are ISO-8601 with offset (`2026-11-18T03:00:00Z`).
- **Only `GET`** on the paths above is allowed. Any other path or method under `/api` (and any
  other path) is denied with **403**. CORS allows `GET`, `HEAD`, `OPTIONS` from the origins in
  `FRONTEND_ORIGIN`.
- **`X-Request-Id`** is set on every response, errors included. A valid incoming `X-Request-Id`
  (1–64 chars of `[A-Za-z0-9-]`) is echoed back; otherwise the server generates a UUID. The same
  id is on the server log line, so quote it when reporting an error.
- **Errors** are RFC 9457 ProblemDetails (`Content-Type: application/problem+json`) and never
  carry stack traces, SQL or exception names:

  | Status | When | Body extras |
  |---|---|---|
  | 400 | Invalid query parameter (see each endpoint) | `title: "Invalid request parameter"`, `parameter: "<name>"` |
  | 400 | Non-numeric value for a numeric parameter (`page`, `size`, `limit`, `minConfidence`, `{id}`) | Spring's standard ProblemDetail (no `parameter` key) |
  | 404 | Unknown card id | `title: "Card not found"` |
  | 429 | Rate limit exceeded | `title: "Too Many Requests"`, `requestId`; `Retry-After` header (seconds) |
  | 500 | Unexpected server error | `detail: "Unexpected server error"`, `requestId` |

  ```json
  {"type":"about:blank","title":"Invalid request parameter","status":400,
   "detail":"intent must be one of: High, Medium, Low, Unspecified",
   "parameter":"intent"}
  ```

  When several parameters are invalid, only the first one checked is reported.
- **Rate limit:** `API_RATE_LIMIT_PER_MINUTE` (default 120) requests per minute per client IP
  on `/api/**`; `/api/health` is exempt.
- **Caching:** `/api/stats` and `/api/cards/facets` send `Cache-Control: public, max-age=<n>`
  on 200 (`API_AGGREGATE_CACHE_MAX_AGE`, default `60s`; `0` = no header). `/api/health` sends
  `no-store`. Other endpoints and all errors keep Spring Security's default (`no-cache, no-store`).
- **Blank parameters** (empty or whitespace) mean "not set" for every filter.

### Paging (list endpoints)

| Param | Type | Default | Limits |
|---|---|---|---|
| `page` | int, 0-based | `0` | 0–10000 |
| `size` | int | `20` | 1–50 (`/api/ingestion-runs`: 1–100) |

Envelope:

```json
{"items": [ ... ], "page": 0, "size": 20, "total_elements": 42, "total_pages": 3}
```

A page past the end returns `200` with `items: []`.

### Shared filter values

| Param | Allowed values | Notes |
|---|---|---|
| `source` | `reddit`, `github`, `hackernews`, `stackexchange`, `g2`, `capterra`, `other` | Case-insensitive, trimmed |
| `intent` | `High`, `Medium`, `Low`, `Unspecified` | Case-insensitive, trimmed |
| `minConfidence` | decimal 0–100 | Inclusive; cards with no score are excluded when set |
| `b2b` | `true`, `false` | Case-insensitive; anything else (`yes`, `1`) is 400 |
| `createdSince` | ISO-8601 date (`2026-11-16` = 00:00 UTC that day) or instant with offset (`2026-11-16T08:00:00Z`, `…+01:00`) | Keeps cards with `created_at` >= the value (inclusive). A future value is valid and returns nothing; a time without offset, epoch numbers or years outside 1–9999 are 400 |
| `q` | 2–100 characters (after trim) | Case-insensitive literal substring of `title`, `problem_statement` or `duct_tape_solutions`; `%` and `_` match literally |

---

## GET /api/health

Liveness probe that also checks the database. No parameters. Not rate limited.
`Cache-Control: no-store`.

| Status | Body |
|---|---|
| 200 | `{"status": "ok", "db": "up"}` |
| 503 | `{"status": "degraded", "db": "down"}` |

The body never includes error details.

## GET /api/stats

Ingestion health snapshot. No parameters. Cacheable (see Conventions).

Per-source maps always contain the four Phase 1 sources (0 / null when empty), then any other
source that has rows. `last_signal_fetched_at` is `null` when nothing was fetched yet;
`last_runs.<source>` has both fields `null` when that source never ran.
`pipeline.failed_extractions` = extractions whose LLM call or parse failed.

```json
{
  "total_cards": 12,
  "cards_by_source": {"reddit": 0, "github": 7, "hackernews": 3, "stackexchange": 2},
  "total_signals": 950,
  "signals_by_source": {"reddit": 0, "github": 610, "hackernews": 220, "stackexchange": 120},
  "unprocessed_signals": 40,
  "last_signal_fetched_at": "2026-11-18T03:05:12Z",
  "last_runs": {
    "reddit": {"last_run_at": null, "last_run_status": null},
    "github": {"last_run_at": "2026-11-18T03:05:12Z", "last_run_status": "Success"}
  },
  "pipeline": {"embedded_signals": 900, "extracted_signals": 880, "pain_points": 310,
               "b2b_pain_points": 240, "failed_extractions": 3}
}
```

## GET /api/ingestion-runs

Recent ingestion runs, newest `started_at` first.

| Param | Type | Default | Allowed |
|---|---|---|---|
| `page`, `size` | int | `0`, `20` | see Paging (`size` max **100**) |
| `source` | string | — | see Shared filter values |
| `status` | string | — | `Success`, `Partial`, `Failed` (case-insensitive) |

400 on: bad `page`/`size`, unknown `source`, unknown `status`.

```json
{"items": [{"id": 31, "source_platform": "github",
            "started_at": "2026-11-18T03:00:00Z", "finished_at": "2026-11-18T03:05:12Z",
            "status": "Success", "fetched_count": 120, "inserted_count": 34,
            "skipped_count": 86, "error_summary": null}],
 "page": 0, "size": 20, "total_elements": 1, "total_pages": 1}
```

`error_summary` is truncated to 500 characters (`…` appended).

## GET /api/cards

Opportunity Cards, paged.

| Param | Type | Default | Allowed |
|---|---|---|---|
| `page`, `size` | int | `0`, `20` | see Paging (`size` max 50) |
| `q` | string | — | see Shared filter values |
| `source` | string | — | see Shared filter values |
| `minConfidence` | decimal | — | 0–100 |
| `intent` | string | — | see Shared filter values |
| `b2b` | string | — | `true` / `false` (filters on `is_b2b_filtered`) |
| `createdSince` | string | — | see Shared filter values ("new this week": `createdSince=2026-11-16`) |
| `sort` | string | `confidence` | `confidence` (highest score first, unscored last, then newest), `newest` (`created_at` desc), `recent` (`last_seen_at` desc, cards without it last) |

400 on any invalid value above (the `parameter` key names it).

Each item is a **Card** object:

```json
{
  "id": 7,
  "title": "Failed webhooks are silently dropped",
  "problem_statement": "Teams lose webhook events when the receiver is briefly down.",
  "trigger_context": "During receiver deploys. Seen in 5 posts across 2 platforms ...",
  "market_size": "Backend developers at small SaaS companies",
  "duct_tape_solutions": "Cron scripts that re-send from logs",
  "economic_intent": "Medium",
  "mvp_wedge": "A retry proxy that stores failed deliveries and replays them ...",
  "confidence_score": 72.5,
  "source_platform": "github",
  "source_url": "https://github.com/org/repo/issues/123",
  "raw_content_snippet": "...",
  "signal_count": 5,
  "platform_count": 2,
  "first_seen_at": "2026-10-02T11:00:00Z",
  "last_seen_at": "2026-11-17T09:30:00Z",
  "created_at": "2026-11-18T03:10:00Z"
}
```

`economic_intent`, `confidence_score`, `signal_count`, `platform_count` and the date fields can be
`null`. The embedding and internal LLM metadata (`llm_model`, `prompt_version`) are never returned.

## GET /api/cards/facets

Card counts per filter option, for the card list's filter chips. Cacheable (see Conventions).

Params: `q`, `source`, `minConfidence`, `intent`, `b2b`, `createdSince` — same values and the same 400s as
[`GET /api/cards`](#get-apicards) (no paging or sort).

- `total` = cards matching **every** filter (equals `/api/cards` `total_elements` for the same
  filters).
- `createdSince` has no map of its own, so it applies to `total` and to every map.
- Each map applies every filter **except its own**, so a count says how many cards selecting that
  option would return.
- `source_platform` always has the four Phase 1 sources (0 when empty), plus other sources that
  have cards. `economic_intent` always has all four values; `is_b2b_filtered` always has `true`
  and `false`. Cards whose intent / B2B flag is `null` count in `total` but in no bucket.

```json
{
  "total": 6,
  "source_platform": {"reddit": 1, "github": 2, "hackernews": 1, "stackexchange": 1, "other": 1},
  "economic_intent": {"High": 2, "Medium": 1, "Low": 1, "Unspecified": 1},
  "is_b2b_filtered": {"true": 3, "false": 2}
}
```

## GET /api/cards/{id}

One Card (same shape as the list items).

| Status | When |
|---|---|
| 200 | Card found |
| 400 | `{id}` is not a number |
| 404 | No card with that id (`detail: "Card <id> not found"`) |

## GET /api/cards/{id}/similar

Cards nearest to `{id}` by embedding (cosine), most similar first. The card itself is not
included.

| Param | Type | Default | Allowed |
|---|---|---|---|
| `limit` | int | `5` | 1–20 |

| Status | When |
|---|---|
| 200 | JSON **array** (no paging envelope); `[]` when the card has no embedding |
| 400 | `limit` out of range or not a number; `{id}` not a number |
| 404 | Unknown card id |

Each element is a Card plus `similarity` (0–1, higher is closer, 4 decimals):

```json
[{"id": 9, "title": "...", "...": "...", "similarity": 0.8731}]
```

## GET /api/cards/{id}/signals

The raw signals (evidence) a card is anchored in, newest `source_created_at` first (unknown dates
last).

| Param | Type | Default | Allowed |
|---|---|---|---|
| `page`, `size` | int | `0`, `20` | see Paging (`size` max 50) |

| Status | When |
|---|---|
| 200 | Paging envelope of Signal objects |
| 400 | Bad `page`/`size`; `{id}` not a number |
| 404 | Unknown card id |

```json
{"items": [{"id": 501, "source_platform": "hackernews",
            "url": "https://news.ycombinator.com/item?id=123",
            "title": "Ask HN: how do you replay failed webhooks?",
            "body_snippet": "First 500 characters of the post ...",
            "score": 42, "comment_count": 17,
            "source_created_at": "2026-11-10T08:00:00Z"}],
 "page": 0, "size": 20, "total_elements": 1, "total_pages": 1}
```

`body_snippet` is at most 500 characters. Authors and content hashes are never returned.
