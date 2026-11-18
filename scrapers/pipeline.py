"""One-shot pipeline: ingest → extract → embed → synthesize.

    python -m scrapers.pipeline [--sources hackernews,github,stackexchange,reddit]
        [--extract-limit 112] [--extract-batch-size 8] [--extract-max-requests 18]
        [--synthesize-limit 2] [--skip-synthesize] [--dry-run]

Runs each module's own ``run()`` in order (no duplicated logic):
1. ``scrapers.ingest --source S`` for every source; sources whose secrets are missing
   (e.g. Reddit before API approval) are skipped with a one-line note.
2. ``scrapers.extract --limit N --batch-size B --max-requests R`` — capped so a day's
   LLM budget is explicit. Free tier, 20 requests/day: up to 18 extraction requests
   (14 batches of 8 = 112 signals, leaving 4 for single-signal retries) + 2 card writes.
3. ``scrapers.embed`` — embeds the B2B pain points extract just found. Embed runs
   *after* extract because it only embeds signals with a pain/B2B extraction; the
   other order would leave today's extractions out of today's cards.
4. ``scrapers.synthesize --limit M`` — clusters → Opportunity Cards.

A failing source or stage is reported and the remaining stages still run. Exit code 0
only if no stage failed (skipped stages do not count as failures). ``--dry-run`` passes
``--dry-run`` to every stage; no stage then makes an LLM/embedding request or writes (IF-85).
Each module prints its own counts; this runner adds one status line per stage, a
final total and (IF-65, read-only) one ``backlog`` line per source: ingested, extracted,
skipped (pre-filter), unprocessed and estimated days to clear at ``--extract-limit``
signals per day. Nothing here prints secrets: notes name variables only.
"""

from __future__ import annotations

import argparse
import logging
import math
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, TextIO

from scrapers import config, embed, extract, ingest, synthesize
from scrapers.adapters.reddit import REQUIRED_VARS as REDDIT_VARS
from scrapers.config import MissingSecretError
from scrapers.http_client import HttpError
from scrapers.store import SupabaseStore

log = logging.getLogger("scrapers.pipeline")

#: Gemini free tier = 20 generate requests/day: 18 for extract + 2 for synthesize.
DEFAULT_EXTRACT_BATCH_SIZE = 8
DEFAULT_EXTRACT_MAX_REQUESTS = 18
#: 14 full batches (14 requests) leave 4 requests for single-signal retries.
DEFAULT_EXTRACT_LIMIT = 14 * DEFAULT_EXTRACT_BATCH_SIZE
DEFAULT_SYNTHESIZE_LIMIT = 2
#: Variables a source needs before it is worth calling (others are optional).
SOURCE_SECRETS: dict[str, tuple[str, ...]] = {
    "hackernews": (),
    "github": ("GITHUB_TOKEN",),
    "stackexchange": ("STACKEXCHANGE_KEY",),
    "reddit": REDDIT_VARS,
}
DEFAULT_SOURCES = ("hackernews", "github", "stackexchange", "reddit")

Stage = Callable[[list[str], TextIO], int]

DEFAULT_STAGES: dict[str, Stage] = {
    "ingest": lambda argv, out: ingest.run(argv, out=out),
    "extract": lambda argv, out: extract.run(argv, out=out),
    "embed": lambda argv, out: embed.run(argv, out=out),
    "synthesize": lambda argv, out: synthesize.run(argv, out=out),
}


BacklogSource = Callable[[], tuple[list[dict[str, Any]], set[int]]]


def _default_backlog() -> tuple[list[dict[str, Any]], set[int]]:
    return SupabaseStore.from_env().fetch_backlog()


@dataclass(frozen=True)
class BacklogRow:
    source: str
    ingested: int
    extracted: int
    skipped: int
    unprocessed: int
    days_to_clear: int | None


def days_to_clear(unprocessed: int, per_day: int) -> int | None:
    """Whole days to classify ``unprocessed`` signals at ``per_day``; None if never."""
    if unprocessed <= 0:
        return 0
    if per_day <= 0:
        return None
    return math.ceil(unprocessed / per_day)


def backlog_rows(signals: Sequence[dict[str, Any]], extracted_ids: set[int],
                 per_day: int) -> list[BacklogRow]:
    """Per-source backlog, sorted by source. ``skipped`` = processed without an
    extraction row (the extract pre-filter, IF-50). Each source's estimate assumes the
    whole daily extract budget; the ``total`` row is the honest shared-budget figure."""
    by_source: dict[str, list[int]] = {}
    for sig in signals:
        src = str(sig.get("source_platform") or "other")
        counts = by_source.setdefault(src, [0, 0, 0])  # ingested, extracted, unprocessed
        counts[0] += 1
        if int(sig["id"]) in extracted_ids:
            counts[1] += 1
        elif not sig.get("processed_at"):
            counts[2] += 1
    rows = [BacklogRow(src, n, e, n - e - u, u, days_to_clear(u, per_day))
            for src, (n, e, u) in sorted(by_source.items())]
    if rows:
        total = [sum(getattr(r, k) for r in rows)
                 for k in ("ingested", "extracted", "skipped", "unprocessed")]
        rows.append(BacklogRow("total", *total, days_to_clear(total[3], per_day)))
    return rows


def print_backlog(source: BacklogSource, per_day: int, out: TextIO) -> None:
    """Read-only; never fails the pipeline (a note is printed instead)."""
    try:
        signals, extracted = source()
    except MissingSecretError as exc:
        print(f"backlog skipped: missing {exc.name}", file=out)
        return
    except HttpError as exc:
        print(f"backlog skipped: read failed (HTTP {exc.status})", file=out)
        return
    for r in backlog_rows(signals, extracted, per_day):
        days = "never" if r.days_to_clear is None else str(r.days_to_clear)
        print(f"backlog source={r.source} ingested={r.ingested} extracted={r.extracted} "
              f"skipped={r.skipped} unprocessed={r.unprocessed} "
              f"days_to_clear={days} per_day={per_day}", file=out)


@dataclass
class StageResult:
    name: str
    status: str  # ok | failed | skipped
    detail: str = ""


def missing_secrets(source: str) -> list[str]:
    return [name for name in SOURCE_SECRETS.get(source, ()) if config.get_env(name) is None]


def _call(stage: Stage, name: str, argv: list[str], out: TextIO) -> StageResult:
    try:
        code = stage(argv, out)
    except SystemExit as exc:  # argparse errors inside a stage
        code = exc.code if isinstance(exc.code, int) else 2
    except Exception as exc:  # noqa: BLE001 - one stage must not stop the others
        log.warning("stage %s crashed: %s", name, type(exc).__name__)
        return StageResult(name, "failed", f"crashed ({type(exc).__name__})")
    return StageResult(name, "ok" if code == 0 else "failed", f"exit={code}")


def run(argv: Sequence[str] | None = None, *,
        stages: dict[str, Stage] | None = None,
        backlog: BacklogSource | None = None,
        out: TextIO = sys.stdout) -> int:
    parser = argparse.ArgumentParser(prog="python -m scrapers.pipeline")
    parser.add_argument("--sources", default=",".join(DEFAULT_SOURCES),
                        help="comma-separated ingest sources")
    parser.add_argument("--extract-limit", type=int, default=DEFAULT_EXTRACT_LIMIT,
                        help="max signals extract handles")
    parser.add_argument("--extract-batch-size", type=int, default=DEFAULT_EXTRACT_BATCH_SIZE,
                        help="signals per extraction request")
    parser.add_argument("--extract-max-requests", type=int,
                        default=DEFAULT_EXTRACT_MAX_REQUESTS,
                        help="max LLM requests for extract")
    parser.add_argument("--synthesize-limit", type=int, default=DEFAULT_SYNTHESIZE_LIMIT,
                        help="max LLM calls for card writing")
    parser.add_argument("--skip-synthesize", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    sources = [s.strip() for s in args.sources.split(",") if s.strip()]
    unknown = [s for s in sources if s not in ingest.ADAPTERS]
    if unknown or not sources:
        parser.error(f"unknown or empty --sources: {unknown} "
                     f"(choose from {', '.join(sorted(ingest.ADAPTERS))})")
    if args.extract_limit < 1:
        parser.error("--extract-limit must be >= 1")
    if args.synthesize_limit < 0:
        parser.error("--synthesize-limit must be >= 0")

    stage = {**DEFAULT_STAGES, **(stages or {})}
    dry = ["--dry-run"] if args.dry_run else []
    results: list[StageResult] = []

    def record(result: StageResult) -> None:
        results.append(result)
        print(f"stage={result.name} status={result.status} {result.detail}".rstrip(), file=out)

    for source in sources:
        name = f"ingest:{source}"
        missing = missing_secrets(source)
        if missing:
            record(StageResult(name, "skipped", f"missing {', '.join(missing)}"))
            continue
        record(_call(stage["ingest"], name, ["--source", source, *dry], out))

    record(_call(stage["extract"], "extract",
                 ["--limit", str(args.extract_limit),
                  "--batch-size", str(args.extract_batch_size),
                  "--max-requests", str(args.extract_max_requests), *dry], out))

    record(_call(stage["embed"], "embed", [*dry], out))

    if args.skip_synthesize:
        record(StageResult("synthesize", "skipped", "--skip-synthesize"))
    else:
        synth_args = dry or ["--limit", str(args.synthesize_limit)]
        record(_call(stage["synthesize"], "synthesize", list(synth_args), out))

    print_backlog(backlog or _default_backlog, args.extract_limit, out)

    counts = {k: sum(1 for r in results if r.status == k) for k in ("ok", "failed", "skipped")}
    status = "success" if counts["failed"] == 0 else "failed"
    print(f"pipeline status={status} stages={len(results)} ok={counts['ok']} "
          f"failed={counts['failed']} skipped={counts['skipped']}", file=out)
    return 0 if status == "success" else 1


def main() -> None:  # pragma: no cover - thin wrapper
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    raise SystemExit(run())


if __name__ == "__main__":  # pragma: no cover
    main()
