"""Ingest CLI: fetch signals from one Phase 1 source and store them in raw_signals.

    python -m scrapers.ingest --source {github,hackernews,reddit,stackexchange}
        [--limit N] [--query Q ...] [--since-days D] [--dry-run]

Prints fetched / inserted / skipped counts. Never prints secrets.
Reddit needs REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET / REDDIT_USER_AGENT; without them
the run exits 2 naming the missing variable and writes nothing.
"""

from __future__ import annotations

import argparse
import itertools
import logging
import sys
from collections.abc import Callable, Iterator, Sequence
from datetime import UTC, datetime, timedelta

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

# Pain-point phrasing that tends to surface B2B / developer friction.
DEFAULT_QUERIES: dict[str, tuple[str, ...]] = {
    "hackernews": ("workaround", "is there a tool", "spreadsheet"),
    "github": ("workaround", "feature request integration"),
    "stackexchange": ("workaround", "export"),
    "reddit": ("workaround", "is there a tool", "spreadsheet"),
}
#: ingestion_runs.status values (CHECK constraint, IF-23 migration).
RUN_STATUS = {"success": "Success", "partial": "Partial", "failed": "Failed"}
DEFAULT_LIMIT = 50
DEFAULT_SINCE_DAYS = 14


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
    parser.add_argument("--since-days", type=int, default=DEFAULT_SINCE_DAYS)
    parser.add_argument("--dry-run", action="store_true",
                        help="fetch and count only; write nothing")
    args = parser.parse_args(argv)
    if args.limit < 1:
        parser.error("--limit must be >= 1")

    started = now()
    since = started - timedelta(days=args.since_days)
    queries = args.queries or DEFAULT_QUERIES[args.source]
    try:
        adapter = (adapter_factory or (lambda s: ADAPTERS[s]()))(args.source)
        store = None if args.dry_run else store_factory()
    except MissingSecretError as exc:
        print(f"error: {exc}", file=out)
        return 2

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
