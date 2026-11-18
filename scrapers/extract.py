"""Extraction CLI: run the LLM extraction prompt over unprocessed raw_signals.

    python -m scrapers.extract [--limit N] [--batch-size B] [--max-requests R] [--dry-run]

Takes raw_signals with processed_at null, ranked by ``scrapers.prioritize`` (cheap,
deterministic, no LLM; IF-50) so the daily budget goes to the likeliest B2B pain posts
first. Signals with almost no text are marked processed without an extraction row
("skipped", counted in the summary) and never consume a request. The best ``--limit``
are sent to the
provider-agnostic LLMClient (LLM_* env vars) in batches of ``--batch-size`` (default 8,
max 15) with prompt ``extract_signal_batch_v1``: one request classifies a whole batch,
which stretches a small daily quota (IF-49). Every returned item is validated with the
extraction schema on its own; valid items are upserted into signal_extractions (with
llm_provider / llm_model / prompt_version) and raw_signals.processed_at is set.

An item that is missing, has an unknown id or is invalid is retried once alone with
``extract_signal_v1``; if still invalid it is recorded as failed: a signal_extractions
row with is_pain_point / is_b2b = null (never clustered) and processed_at set, so it is
not retried forever. ``--batch-size 1`` is the old per-signal mode (v1, one retry).
Provider/network errors leave the signals unprocessed for the next run; after
``MAX_CONSECUTIVE_PROVIDER_ERRORS`` in a row the run stops. A quota-exhausted response
stops the run at once (results already validated are kept). ``--max-requests`` caps LLM
requests per run so a day's budget is explicit; signals beyond it wait for the next run.

``--dry-run`` makes no LLM requests and writes nothing: it prints the plan (signals that
would be sent, batch count, requests that would be used against ``--max-requests``) and
exits 0, so a smoke test never spends the daily quota (IF-85).

Post text is untrusted: fenced in <signal> tags and the system prompt forbids
following instructions inside it. Never prints secrets or post content.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from scrapers import prioritize
from scrapers.config import MissingSecretError
from scrapers.http_client import HttpError, QuotaExhausted
from scrapers.llm.base import LLMClient, ProviderNotSupportedError
from scrapers.llm.extraction_schema import (
    ExtractionValidationError,
    parse_json,
    validate_extraction,
)
from scrapers.llm.factory import llm_client_from_env
from scrapers.llm.prompts import extract_signal_batch_v1 as prompt_batch
from scrapers.llm.prompts import extract_signal_v1 as prompt_v1
from scrapers.store import SupabaseStore

log = logging.getLogger("scrapers.extract")

DEFAULT_LIMIT = 40
DEFAULT_BATCH_SIZE = prompt_batch.DEFAULT_BATCH_SIZE
MAX_BATCH_SIZE = prompt_batch.MAX_BATCH_SIZE
MAX_ATTEMPTS = 2  # single-signal mode: first try + one retry on invalid output
MAX_CONSECUTIVE_PROVIDER_ERRORS = 3


class BudgetExhausted(Exception):
    """--max-requests reached; remaining signals wait for the next run."""


class Budget:
    """Counts LLM requests and enforces the optional per-run cap."""

    def __init__(self, llm: LLMClient, max_requests: int | None) -> None:
        self.llm, self.max_requests, self.used = llm, max_requests, 0

    def complete(self, system: str, prompt: str) -> str:
        if self.max_requests is not None and self.used >= self.max_requests:
            raise BudgetExhausted
        self.used += 1
        return self.llm.complete(system, prompt, json_mode=True)


@dataclass
class ExtractStats:
    processed: int = 0
    pain_points: int = 0
    b2b_pain_points: int = 0
    failed_validation: int = 0
    provider_errors: int = 0
    batched_ok: int = 0
    retried_alone: int = 0

    @property
    def validation_pass_rate(self) -> float:
        return 0.0 if not self.processed else 1 - self.failed_validation / self.processed


def extract_one(llm: LLMClient | Budget, signal: dict[str, Any], *,
                attempts: int = MAX_ATTEMPTS) -> dict[str, Any] | None:
    """Validated extraction for one signal (prompt v1), or None if output stayed invalid.

    Provider errors (HttpError / RuntimeError) propagate to the caller.
    """
    budget = llm if isinstance(llm, Budget) else Budget(llm, None)
    prompt = prompt_v1.build_prompt(signal.get("source_platform") or "other",
                                    signal.get("title"), signal.get("body"),
                                    signal.get("tags"))
    for attempt in range(1, attempts + 1):
        reply = budget.complete(prompt_v1.SYSTEM, prompt)
        try:
            return validate_extraction(parse_json(reply))
        except ExtractionValidationError as exc:
            log.warning("signal %s: invalid extraction (attempt %d): %s",
                        signal.get("id"), attempt, exc)
    return None


def _item_id(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def parse_batch(reply: str, ids: Sequence[int]) -> dict[int, dict[str, Any]]:
    """Valid extractions by signal id from a batch reply.

    Unknown ids, duplicates (first occurrence wins) and invalid items are dropped; the
    caller retries every requested id that is absent from the result.
    """
    try:
        data = parse_json(reply)
    except ExtractionValidationError as exc:
        log.warning("batch reply is not valid JSON: %s", exc)
        return {}
    if isinstance(data, dict):  # tolerate {"results": [...]}: one key holding the array
        lists = [v for v in data.values() if isinstance(v, list)]
        data = lists[0] if len(data) == 1 and lists else None
    if not isinstance(data, list):
        log.warning("batch reply is not a JSON array")
        return {}
    wanted, seen = set(ids), set()
    out: dict[int, dict[str, Any]] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        sid = _item_id(item.get("id"))
        if sid is None or sid not in wanted or sid in seen:
            if sid is not None and sid not in wanted:
                log.warning("batch reply has unrequested id %s; ignored", sid)
            continue
        seen.add(sid)
        try:
            out[sid] = validate_extraction({k: v for k, v in item.items() if k != "id"})
        except ExtractionValidationError as exc:
            log.warning("signal %s: invalid batch item: %s", sid, exc)
    return out


def extraction_row(signal_id: int, llm: LLMClient, result: dict[str, Any] | None,
                   prompt_version: str = prompt_v1.PROMPT_VERSION) -> dict[str, Any]:
    base = {"signal_id": signal_id, "llm_provider": llm.provider, "llm_model": llm.model,
            "prompt_version": prompt_version}
    if result is None:  # recorded as failed: null classification, never clustered
        return {**base, "is_pain_point": None, "is_b2b": None, "problem_summary": None,
                "duct_tape": None, "economic_intent": None, "persona": None,
                "workflow_tags": None}
    return {**base, **result}


def _chunks(items: Sequence[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [list(items[i:i + size]) for i in range(0, len(items), size)]


class _Stop(Exception):
    """Ends the run early with a message already printed."""


class _StoreFailed(Exception):
    pass


class Runner:
    def __init__(self, llm: LLMClient, store: SupabaseStore, budget: Budget,
                 now: Callable[[], datetime], dry_run: bool, out) -> None:
        self.llm, self.store, self.budget = llm, store, budget
        self.now, self.dry_run, self.out = now, dry_run, out
        self.stats = ExtractStats()
        self.consecutive_errors = 0

    def record(self, signal: dict[str, Any], result: dict[str, Any] | None,
               version: str) -> None:
        self.consecutive_errors = 0
        stats = self.stats
        stats.processed += 1
        if result is None:
            stats.failed_validation += 1
        elif result["is_pain_point"]:
            stats.pain_points += 1
            stats.b2b_pain_points += int(result["is_b2b"])
        if self.dry_run:
            return
        try:
            self.store.save_extraction(
                extraction_row(int(signal["id"]), self.llm, result, version))
            self.store.mark_processed(int(signal["id"]), self.now())
        except HttpError as exc:
            print(f"error: could not store extraction (HTTP {exc.status})", file=self.out)
            raise _StoreFailed from exc

    def provider_error(self, exc: Exception, what: str) -> None:
        """Count a provider error; raise _Stop on quota/budget or too many in a row."""
        if isinstance(exc, BudgetExhausted):
            print(f"note: --max-requests {self.budget.max_requests} reached; remaining "
                  "signals are left for the next run", file=self.out)
            raise _Stop
        self.stats.provider_errors += 1
        if isinstance(exc, QuotaExhausted):
            print(f"error: LLM quota exhausted (HTTP {exc.status}); stopping — "
                  "remaining signals are left for the next run", file=self.out)
            raise _Stop
        self.consecutive_errors += 1
        status = exc.status if isinstance(exc, HttpError) else "n/a"
        log.warning("%s: provider error (HTTP %s); left unprocessed", what, status)
        if self.consecutive_errors >= MAX_CONSECUTIVE_PROVIDER_ERRORS:
            print("error: stopping after repeated provider errors", file=self.out)
            raise _Stop

    def single(self, signal: dict[str, Any], attempts: int) -> None:
        try:
            result = extract_one(self.budget, signal, attempts=attempts)
        except (BudgetExhausted, HttpError, RuntimeError) as exc:
            self.provider_error(exc, f"signal {signal.get('id')}")
            return
        self.record(signal, result, prompt_v1.PROMPT_VERSION)

    def batch(self, batch: list[dict[str, Any]]) -> None:
        if len(batch) == 1:  # one signal: the v1 per-signal prompt is the same request
            self.single(batch[0], MAX_ATTEMPTS)
            return
        ids = [int(s["id"]) for s in batch]
        try:
            reply = self.budget.complete(prompt_batch.SYSTEM, prompt_batch.build_prompt(batch))
        except (BudgetExhausted, HttpError, RuntimeError) as exc:
            self.provider_error(exc, f"batch {ids[0]}..{ids[-1]}")
            return
        results = parse_batch(reply, ids)
        for signal in batch:
            result = results.get(int(signal["id"]))
            if result is not None:
                self.stats.batched_ok += 1
                self.record(signal, result, prompt_batch.PROMPT_VERSION)
        for signal in batch:
            if int(signal["id"]) not in results:
                self.stats.retried_alone += 1
                self.single(signal, 1)


def print_plan(llm: LLMClient, args: argparse.Namespace, ranked: Sequence[dict[str, Any]],
               skipped: Sequence[dict[str, Any]], signals: Sequence[dict[str, Any]],
               out) -> None:
    """Dry-run summary: what a real run would send. Makes no LLM request."""
    batches = len(_chunks(signals, args.batch_size))
    planned = batches if args.max_requests is None else min(batches, args.max_requests)
    cap = "none" if args.max_requests is None else str(args.max_requests)
    prompt = prompt_v1.PROMPT_VERSION if args.batch_size == 1 else prompt_batch.PROMPT_VERSION
    print(
        f"extract mode=dry-run provider={llm.provider} model={llm.model} "
        f"prompt={prompt} batch_size={args.batch_size} unprocessed={len(ranked)} "
        f"skipped={len(skipped)} candidates={len(signals)} batches={batches} "
        f"planned_requests={planned} max_requests={cap} requests=0 "
        "(retries of invalid items not counted)",
        file=out,
    )


def run(argv: Sequence[str] | None = None, *,
        llm_factory: Callable[[], LLMClient] = llm_client_from_env,
        store_factory: Callable[[], SupabaseStore] = SupabaseStore.from_env,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        out=sys.stdout) -> int:
    parser = argparse.ArgumentParser(prog="python -m scrapers.extract")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                        help="max signals this run")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
                        help=f"signals per LLM request (1-{MAX_BATCH_SIZE})")
    parser.add_argument("--max-requests", type=int, default=None,
                        help="max LLM requests this run (default: no cap)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the plan; no LLM requests, no writes")
    args = parser.parse_args(argv)
    if args.limit < 1:
        parser.error("--limit must be >= 1")
    if not 1 <= args.batch_size <= MAX_BATCH_SIZE:
        parser.error(f"--batch-size must be between 1 and {MAX_BATCH_SIZE}")
    if args.max_requests is not None and args.max_requests < 1:
        parser.error("--max-requests must be >= 1")

    try:
        store = store_factory()
        llm = llm_factory()
    except (MissingSecretError, ProviderNotSupportedError) as exc:
        print(f"error: {exc}", file=out)
        return 2

    try:
        ranked, skipped = prioritize.plan(store.fetch_unprocessed_pool())
    except HttpError as exc:
        print(f"error: could not read raw_signals (HTTP {exc.status})", file=out)
        return 1
    signals = ranked[:args.limit]
    if args.dry_run:
        print_plan(llm, args, ranked, skipped, signals, out)
        return 0
    try:
        for sig in skipped:  # processed_at set, no extraction row = pre-filter skip
            store.mark_processed(int(sig["id"]), now())
    except HttpError as exc:
        print(f"error: could not mark skipped signals (HTTP {exc.status})", file=out)
        return 1

    runner = Runner(llm, store, Budget(llm, args.max_requests), now, False, out)
    try:
        for batch in _chunks(signals, args.batch_size):
            runner.batch(batch)
    except _Stop:
        pass
    except _StoreFailed:
        return 1

    stats = runner.stats
    mode = "stored"
    prompt = prompt_v1.PROMPT_VERSION if args.batch_size == 1 else prompt_batch.PROMPT_VERSION
    print(
        f"extract mode={mode} provider={llm.provider} model={llm.model} "
        f"prompt={prompt} batch_size={args.batch_size} unprocessed={len(ranked)} "
        f"skipped={len(skipped)} candidates={len(signals)} "
        f"requests={runner.budget.used} batched_ok={stats.batched_ok} "
        f"retried_alone={stats.retried_alone} "
        f"processed={stats.processed} pain_points={stats.pain_points} "
        f"b2b_pain_points={stats.b2b_pain_points} failed={stats.failed_validation} "
        f"provider_errors={stats.provider_errors} "
        f"validation_pass_rate={stats.validation_pass_rate:.2f}",
        file=out,
    )
    return 0 if stats.provider_errors == 0 else 1


def main() -> None:  # pragma: no cover - thin wrapper
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    raise SystemExit(run())


if __name__ == "__main__":  # pragma: no cover
    main()
