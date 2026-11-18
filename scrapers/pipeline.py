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
``--dry-run`` to ingest, embed and synthesize and skips extract (it would spend LLM quota).
Each module prints its own counts; this runner adds one status line per stage and a
final total. Nothing here prints secrets: notes name variables only.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TextIO

from scrapers import config, embed, extract, ingest, synthesize
from scrapers.adapters.reddit import REQUIRED_VARS as REDDIT_VARS

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

    if args.dry_run:
        record(StageResult("extract", "skipped", "dry-run (would spend LLM quota)"))
    else:
        record(_call(stage["extract"], "extract",
                     ["--limit", str(args.extract_limit),
                      "--batch-size", str(args.extract_batch_size),
                      "--max-requests", str(args.extract_max_requests)], out))

    record(_call(stage["embed"], "embed", [*dry], out))

    if args.skip_synthesize:
        record(StageResult("synthesize", "skipped", "--skip-synthesize"))
    else:
        synth_args = dry or ["--limit", str(args.synthesize_limit)]
        record(_call(stage["synthesize"], "synthesize", list(synth_args), out))

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
