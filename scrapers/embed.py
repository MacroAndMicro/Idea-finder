"""Embedding CLI: embed raw_signals for clustering (backfill + incremental).

    python -m scrapers.embed [--limit N] [--all] [--dry-run]

Selects raw_signals with ``embedding`` null and embeds ``title + body`` (truncated to
``MAX_EMBED_CHARS``) through the provider-agnostic EmbeddingClient (EMBEDDING_* env
vars, exactly 1536 dimensions), then writes ``embedding`` + ``embedding_model``.

Which signals: by default only signals whose extraction says ``is_pain_point`` and
``is_b2b`` — the only ones clustering uses (scrapers/cluster.py), so we don't pay to
embed noise. Signals with no extraction yet are skipped until `scrapers.extract`
has run. ``--all`` embeds every signal with a null embedding regardless (backfill).
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Callable, Sequence
from typing import Any

from scrapers.config import MissingSecretError
from scrapers.http_client import HttpError
from scrapers.llm.base import (
    EmbeddingClient,
    EmbeddingDimensionError,
    ProviderNotSupportedError,
    check_dimensions,
)
from scrapers.llm.factory import embedding_client_from_env
from scrapers.store import SupabaseStore

log = logging.getLogger("scrapers.embed")

DEFAULT_LIMIT = 100
BATCH_SIZE = 32          # texts per embedding request
MAX_EMBED_CHARS = 8000   # title + body; keeps requests within common model input limits


def embed_text(signal: dict[str, Any]) -> str:
    title = (signal.get("title") or "").strip()
    body = (signal.get("body") or "").strip()
    text = f"{title}\n\n{body}".strip() if body else title
    return text[:MAX_EMBED_CHARS]


def vector_literal(vec: Sequence[float]) -> str:
    """pgvector text form, e.g. '[0.1,0.2]'. Rejects anything but 1536 dims."""
    check_dimensions(len(vec))
    return "[" + ",".join(repr(float(v)) for v in vec) + "]"


def run(argv: Sequence[str] | None = None, *,
        embedder_factory: Callable[[], EmbeddingClient] = embedding_client_from_env,
        store_factory: Callable[[], SupabaseStore] = SupabaseStore.from_env,
        out=sys.stdout) -> int:
    parser = argparse.ArgumentParser(prog="python -m scrapers.embed")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--all", action="store_true", dest="all_signals",
                        help="embed every signal with a null embedding, not only B2B pain")
    parser.add_argument("--dry-run", action="store_true",
                        help="embed but write nothing")
    args = parser.parse_args(argv)
    if args.limit < 1:
        parser.error("--limit must be >= 1")

    try:
        store = store_factory()
        embedder = embedder_factory()
    except (MissingSecretError, ProviderNotSupportedError, EmbeddingDimensionError) as exc:
        print(f"error: {exc}", file=out)
        return 2

    try:
        signals = store.fetch_signals_to_embed(args.limit, pain_only=not args.all_signals)
    except HttpError as exc:
        print(f"error: could not read raw_signals (HTTP {exc.status})", file=out)
        return 1

    embedded = skipped = 0
    status = "success"
    candidates = [s for s in signals if embed_text(s)]
    skipped = len(signals) - len(candidates)
    for start in range(0, len(candidates), BATCH_SIZE):
        batch = candidates[start:start + BATCH_SIZE]
        try:
            vectors = embedder.embed([embed_text(s) for s in batch])
            if not args.dry_run:
                for signal, vec in zip(batch, vectors, strict=True):
                    store.save_signal_embedding(int(signal["id"]), vector_literal(vec),
                                                embedder.embedding_model)
        except EmbeddingDimensionError as exc:
            print(f"error: {exc}", file=out)
            status = "failed"
            break
        except (HttpError, RuntimeError) as exc:
            code = exc.status if isinstance(exc, HttpError) else "n/a"
            print(f"error: embedding/store request failed (HTTP {code})", file=out)
            status = "failed"
            break
        embedded += len(batch)

    mode = "dry-run" if args.dry_run else "stored"
    scope = "all" if args.all_signals else "b2b-pain"
    print(f"embed mode={mode} scope={scope} model={embedder.embedding_model} "
          f"candidates={len(signals)} embedded={embedded} skipped_empty={skipped} "
          f"status={status}", file=out)
    return 0 if status == "success" else 1


def main() -> None:  # pragma: no cover - thin wrapper
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    raise SystemExit(run())


if __name__ == "__main__":  # pragma: no cover
    main()
