"""Ingest CLI: fetch signals from one Phase 1 source and store them in raw_signals.

    python -m scrapers.ingest --source {github,hackernews,reddit,stackexchange}
        [--limit N] [--query Q ...] [--since-days D] [--dry-run]

Default queries (and Stack Exchange sites / Reddit subreddits) come from the reviewed
file ``scrapers/queries.toml`` (IF-51); ``--query`` overrides the queries, and
STACKEXCHANGE_SITES / REDDIT_SUBREDDITS override the site lists.
Prints fetched / inserted / skipped counts. Never prints secrets.
Reddit needs REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET / REDDIT_USER_AGENT; without them
the run exits 2 naming the missing variable and writes nothing.
"""

from __future__ import annotations

import argparse
import itertools
import logging
import sys
import tomllib
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scrapers import config
from scrapers.adapters.base import SourceAdapter
from scrapers.adapters.github import GitHubIssuesAdapter
from scrapers.adapters.hackernews import HackerNewsAdapter
from scrapers.adapters.reddit import RedditAdapter
from scrapers.adapters.stackexchange import StackExchangeAdapter
from scrapers.config import MissingSecretError
from scrapers.http_client import HttpError, RateLimitExceeded
from scrapers.models import RawSignal
from scrapers.store import StoreResult, SupabaseStore

log = logging.getLogger("scrapers.ingest")

ADAPTERS: dict[str, Callable[[], SourceAdapter]] = {
    "hackernews": HackerNewsAdapter,
    "github": GitHubIssuesAdapter.from_env,
    "stackexchange": StackExchangeAdapter.from_env,
    "reddit": RedditAdapter.from_env,
}
REQUIRED_KEY = {"github": "GITHUB_TOKEN", "stackexchange": "STACKEXCHANGE_KEY"}

QUERIES_FILE = Path(__file__).with_name("queries.toml")
#: Optional list keys per source in queries.toml → (adapter kwarg, overriding env var).
SOURCE_LISTS: dict[str, dict[str, tuple[str, str]]] = {
    "stackexchange": {"sites": ("sites", "STACKEXCHANGE_SITES")},
    "reddit": {"subreddits": ("subreddits", "REDDIT_SUBREDDITS")},
}


class QueryConfigError(ValueError):
    pass


@dataclass(frozen=True)
class SourceQueries:
    queries: tuple[str, ...]
    lists: Mapping[str, tuple[str, ...]]


def _str_list(source: str, key: str, value: object) -> tuple[str, ...]:
    if (not isinstance(value, list) or not value
            or not all(isinstance(v, str) and v.strip() for v in value)):
        raise QueryConfigError(f"[{source}] {key} must be a non-empty list of strings")
    return tuple(v.strip() for v in value)


def load_queries(path: Path = QUERIES_FILE) -> dict[str, SourceQueries]:
    """Parse queries.toml; every ingest source needs an entry and no other source may appear."""
    with path.open("rb") as fh:
        data = tomllib.load(fh)
    unknown = sorted(set(data) - set(ADAPTERS))
    missing = sorted(set(ADAPTERS) - set(data))
    if unknown or missing:
        raise QueryConfigError(f"queries file: unknown sources {unknown}, missing {missing}")
    out: dict[str, SourceQueries] = {}
    for source, table in data.items():
        if not isinstance(table, dict):
            raise QueryConfigError(f"[{source}] must be a table")
        allowed = {"queries", *SOURCE_LISTS.get(source, {})}
        extra = sorted(set(table) - allowed)
        if extra:
            raise QueryConfigError(f"[{source}] unknown keys {extra}")
        lists = {k: _str_list(source, k, table[k]) for k in table if k != "queries"}
        out[source] = SourceQueries(_str_list(source, "queries", table.get("queries")), lists)
    return out


QUERY_CONFIG = load_queries()
#: Pain-point phrasing that tends to surface B2B / developer friction (from queries.toml).
DEFAULT_QUERIES: dict[str, tuple[str, ...]] = {s: c.queries for s, c in QUERY_CONFIG.items()}


def adapter_kwargs(source: str, cfg: Mapping[str, SourceQueries] = QUERY_CONFIG
                   ) -> dict[str, list[str]]:
    """Site / subreddit lists from queries.toml, unless their env var overrides them."""
    kwargs: dict[str, list[str]] = {}
    for key, (kwarg, env) in SOURCE_LISTS.get(source, {}).items():
        values = cfg[source].lists.get(key)
        if values and config.get_env(env) is None:
            kwargs[kwarg] = list(values)
    return kwargs
#: ingestion_runs.status values (CHECK constraint, IF-23 migration).
RUN_STATUS = {"success": "Success", "partial": "Partial", "failed": "Failed"}
DEFAULT_LIMIT = 50
DEFAULT_SINCE_DAYS = 14
#: Overlap subtracted from the last successful run's start so items published while that
#: run was in flight are not missed (re-fetches are skipped as duplicates by the store).
SINCE_OVERLAP = timedelta(hours=1)


def choose_since(started: datetime, source: str, since_days: int | None,
                 store: object | None) -> tuple[datetime, str]:
    """Look-back window for this run and why (IF-75).

    ``flag``: explicit --since-days wins. ``last_success``: started_at of the latest
    Success run for the source minus SINCE_OVERLAP, never further back than
    DEFAULT_SINCE_DAYS. ``default``: DEFAULT_SINCE_DAYS when there is no such run, no
    store (dry-run / Supabase not configured) or the lookup fails.
    """
    if since_days is not None:
        return started - timedelta(days=since_days), "flag"
    floor = started - timedelta(days=DEFAULT_SINCE_DAYS)
    last = None
    lookup = getattr(store, "last_success_started_at", None)
    if lookup is not None:
        try:
            last = lookup(source)
        except HttpError as exc:
            log.warning("last successful run lookup failed (HTTP %s); using default window",
                        exc.status)
    if last is None:
        return floor, "default"
    if last.tzinfo is None:
        last = last.replace(tzinfo=UTC)
    return max(floor, min(started, last - SINCE_OVERLAP)), "last_success"


def collect(adapter: SourceAdapter, queries: Sequence[str], since: datetime,
            limit: int) -> Iterator[RawSignal]:
    """Signals across queries, de-duplicated by external_id, capped at ``limit``."""
    seen: set[str] = set()

    def stream() -> Iterator[RawSignal]:
        for query in queries:
            for signal in adapter.fetch(query, since):
                if signal.external_id not in seen:
                    seen.add(signal.external_id)
                    yield signal

    return itertools.islice(stream(), limit)


def error_summary(source: str, stage: str, exc: HttpError) -> str:
    """Short, secret-free reason for ingestion_runs.error_summary.

    Never ``str(exc)``: it can embed a request URL (e.g. Stack Exchange ``key=``).
    """
    if exc.status == 0:
        reason = "network error"
    elif isinstance(exc, RateLimitExceeded):
        reason = f"rate limited (HTTP {exc.status})"
    else:
        reason = f"HTTP {exc.status}"
    return f"{stage} {source}: {reason}"


def run(argv: Sequence[str] | None = None, *,
        adapter_factory: Callable[[str], SourceAdapter] | None = None,
        store_factory: Callable[[], SupabaseStore] = SupabaseStore.from_env,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        out=sys.stdout) -> int:
    parser = argparse.ArgumentParser(prog="python -m scrapers.ingest")
    parser.add_argument("--source", required=True, choices=sorted(ADAPTERS))
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--query", action="append", dest="queries")
    parser.add_argument("--since-days", type=int, default=None,
                        help=f"look-back in days (default: since the last successful run "
                             f"for the source, at most {DEFAULT_SINCE_DAYS})")
    parser.add_argument("--dry-run", action="store_true",
                        help="fetch and count only; write nothing")
    args = parser.parse_args(argv)
    if args.limit < 1:
        parser.error("--limit must be >= 1")
    if args.since_days is not None and args.since_days < 0:
        parser.error("--since-days must be >= 0")

    started = now()
    queries = args.queries or DEFAULT_QUERIES[args.source]
    try:
        adapter = (adapter_factory or (lambda s: ADAPTERS[s](**adapter_kwargs(s))))(args.source)
        store = None if args.dry_run else store_factory()
    except MissingSecretError as exc:
        print(f"error: {exc}", file=out)
        return 2

    since, since_reason = choose_since(started, args.source, args.since_days, store)
    print(f"since={since.isoformat()} reason={since_reason}", file=out)

    status, error, summary = "success", None, None
    fetched: list[RawSignal] = []
    result = StoreResult()
    try:
        for signal in collect(adapter, queries, since, args.limit):
            fetched.append(signal)
    except HttpError as exc:  # keep what was fetched before the API gave up
        status, error = "partial" if fetched else "failed", str(exc)
        summary = error_summary(args.source, "fetch", exc)
    try:
        if store is not None and fetched:
            result = store.upsert_signals(fetched)
    except HttpError as exc:
        status, error = "failed", str(exc)
        summary = error_summary(args.source, "store", exc)

    if not fetched and args.source in REQUIRED_KEY and status == "success":
        print(f"note: 0 signals — is {REQUIRED_KEY[args.source]} set?", file=out)

    mode = "dry-run" if args.dry_run else "stored"
    print(
        f"source={args.source} mode={mode} fetched={len(fetched)} "
        f"inserted={result.inserted} skipped={result.skipped} status={status}",
        file=out,
    )
    if error:
        print(f"error: {error}", file=out)

    if store is not None:
        store.record_run({
            "source_platform": args.source,
            "started_at": started.isoformat(),
            "finished_at": now().isoformat(),
            "status": RUN_STATUS[status],
            "fetched_count": len(fetched),
            "inserted_count": result.inserted,
            "skipped_count": result.skipped,
            "error_summary": summary,
        })
    return 0 if status == "success" else 1


def main() -> None:  # pragma: no cover - thin wrapper
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    raise SystemExit(run())


if __name__ == "__main__":  # pragma: no cover
    main()
