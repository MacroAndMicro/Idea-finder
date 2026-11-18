"""Extraction CLI: run the per-signal LLM prompt over unprocessed raw_signals.

    python -m scrapers.extract [--limit N] [--dry-run]

For each raw_signals row with processed_at null (oldest first): build the versioned
prompt, call the provider-agnostic LLMClient (LLM_* env vars), validate the JSON,
upsert signal_extractions (with llm_provider / llm_model / prompt_version) and set
raw_signals.processed_at.

Invalid model output is retried once; if it is still invalid the signal is recorded
as failed: a signal_extractions row with is_pain_point / is_b2b = null (so it is
never clustered) and processed_at set, so it is not retried forever.
Provider/network errors leave the signal unprocessed for the next run; after
``MAX_CONSECUTIVE_PROVIDER_ERRORS`` in a row the run stops. A quota-exhausted
response (e.g. a per-day free-tier limit) stops the run at once: retrying would only
burn requests.

Post text is untrusted: it is fenced in <signal> tags and the system prompt forbids
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

from scrapers.config import MissingSecretError
from scrapers.http_client import HttpError, QuotaExhausted
from scrapers.llm.base import LLMClient, ProviderNotSupportedError
from scrapers.llm.extraction_schema import (
    ExtractionValidationError,
    parse_json,
    validate_extraction,
)
from scrapers.llm.factory import llm_client_from_env
from scrapers.llm.prompts import extract_signal_v1 as prompt_v1
from scrapers.store import SupabaseStore

log = logging.getLogger("scrapers.extract")

DEFAULT_LIMIT = 25
MAX_ATTEMPTS = 2  # first try + one retry on invalid output
MAX_CONSECUTIVE_PROVIDER_ERRORS = 3


@dataclass
class ExtractStats:
    processed: int = 0
    pain_points: int = 0
    b2b_pain_points: int = 0
    failed_validation: int = 0
    provider_errors: int = 0

    @property
    def validation_pass_rate(self) -> float:
        return 0.0 if not self.processed else 1 - self.failed_validation / self.processed


def extract_one(llm: LLMClient, signal: dict[str, Any]) -> dict[str, Any] | None:
    """Validated extraction for one signal, or None if output stayed invalid.

    Provider errors (HttpError / RuntimeError) propagate to the caller.
    """
    prompt = prompt_v1.build_prompt(signal.get("source_platform") or "other",
                                    signal.get("title"), signal.get("body"),
                                    signal.get("tags"))
    for attempt in range(1, MAX_ATTEMPTS + 1):
        reply = llm.complete(prompt_v1.SYSTEM, prompt, json_mode=True)
        try:
            return validate_extraction(parse_json(reply))
        except ExtractionValidationError as exc:
            log.warning("signal %s: invalid extraction (attempt %d): %s",
                        signal.get("id"), attempt, exc)
    return None


def extraction_row(signal_id: int, llm: LLMClient,
                   result: dict[str, Any] | None) -> dict[str, Any]:
    base = {"signal_id": signal_id, "llm_provider": llm.provider, "llm_model": llm.model,
            "prompt_version": prompt_v1.PROMPT_VERSION}
    if result is None:  # recorded as failed: null classification, never clustered
        return {**base, "is_pain_point": None, "is_b2b": None, "problem_summary": None,
                "duct_tape": None, "economic_intent": None, "persona": None,
                "workflow_tags": None}
    return {**base, **result}


def run(argv: Sequence[str] | None = None, *,
        llm_factory: Callable[[], LLMClient] = llm_client_from_env,
        store_factory: Callable[[], SupabaseStore] = SupabaseStore.from_env,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        out=sys.stdout) -> int:
    parser = argparse.ArgumentParser(prog="python -m scrapers.extract")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--dry-run", action="store_true",
                        help="call the LLM and validate, but write nothing")
    args = parser.parse_args(argv)
    if args.limit < 1:
        parser.error("--limit must be >= 1")

    try:
        store = store_factory()
        llm = llm_factory()
    except (MissingSecretError, ProviderNotSupportedError) as exc:
        print(f"error: {exc}", file=out)
        return 2

    try:
        signals = store.fetch_unprocessed_signals(args.limit)
    except HttpError as exc:
        print(f"error: could not read raw_signals (HTTP {exc.status})", file=out)
        return 1

    stats = ExtractStats()
    consecutive_errors = 0
    for signal in signals:
        try:
            result = extract_one(llm, signal)
        except QuotaExhausted as exc:
            stats.provider_errors += 1
            print(f"error: LLM quota exhausted (HTTP {exc.status}); stopping — "
                  "remaining signals are left for the next run", file=out)
            break
        except (HttpError, RuntimeError) as exc:
            stats.provider_errors += 1
            consecutive_errors += 1
            status = exc.status if isinstance(exc, HttpError) else "n/a"
            log.warning("signal %s: provider error (HTTP %s); left unprocessed",
                        signal.get("id"), status)
            if consecutive_errors >= MAX_CONSECUTIVE_PROVIDER_ERRORS:
                print("error: stopping after repeated provider errors", file=out)
                break
            continue
        consecutive_errors = 0
        stats.processed += 1
        if result is None:
            stats.failed_validation += 1
        elif result["is_pain_point"]:
            stats.pain_points += 1
            stats.b2b_pain_points += int(result["is_b2b"])
        if args.dry_run:
            continue
        try:
            store.save_extraction(extraction_row(int(signal["id"]), llm, result))
            store.mark_processed(int(signal["id"]), now())
        except HttpError as exc:
            print(f"error: could not store extraction (HTTP {exc.status})", file=out)
            return 1

    mode = "dry-run" if args.dry_run else "stored"
    print(
        f"extract mode={mode} provider={llm.provider} model={llm.model} "
        f"prompt={prompt_v1.PROMPT_VERSION} candidates={len(signals)} "
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
