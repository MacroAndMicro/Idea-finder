"""Synthesis CLI: turn clusters of B2B pain-point signals into Opportunity Cards.

    python -m scrapers.synthesize [--min-signals N] [--limit N] [--threshold T] [--dry-run]

1. Load embedded raw_signals whose extraction is ``is_pain_point`` and ``is_b2b``.
2. Cluster them (``scrapers.cluster``) and keep clusters with >= ``--min-signals``.
3. For each cluster (highest confidence first):
   - **Already carded** (>= ``OVERLAP_MATCH`` of its signals are linked to one card):
     link any new signals and refresh the card's counts, dates, confidence and the
     frequency sentence of ``trigger_context``. No LLM call. Nothing new → unchanged.
   - **New**: the LLM (prompt ``synthesize_card_v1``) writes title + narrative fields
     from the cluster's evidence only; output is schema-validated (one retry), then
     the row is checked by the deterministic quality gate (``scrapers.card_quality``,
     IF-62): any failed rule keeps it out and the cluster is remembered with reason
     ``quality:<rules>``. The card text is embedded and compared with existing
     cards: cosine similarity >=
     ``CARD_DUPLICATE_THRESHOLD`` → merged into that card instead of inserting.
     Otherwise a new ``opportunity_cards`` row + its ``card_signals`` links are written
     atomically (SQL function ``insert_card_with_links``, IF-48).
   - **Rejected before** (IF-48): a cluster the LLM rejected (``valid_opportunity``
     false) or answered invalidly is remembered in ``synthesis_rejections`` by its
     fingerprint (prompt version + sorted signal ids) and skipped with no LLM call until
     its signal set (or the prompt) changes, so it cannot eat the daily budget forever.

Never invented by the model: counts, platforms, dates (computed here and appended to
``trigger_context``), ``economic_intent`` (strongest intent stated in the cluster's
extractions), ``confidence_score`` (``cluster.confidence_score``) and provenance
(source_platform = dominant platform; source_url / raw_content_snippet from the
strongest signal by score + comments).

``--limit`` caps LLM calls per run (free-tier quotas); clusters over the cap are
left for the next run. ``--dry-run`` clusters and reports, with no LLM call and no write.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from scrapers.card_quality import RULES as QUALITY_RULES
from scrapers.card_quality import EvidenceText, check_card, rejection_reason
from scrapers.cluster import (
    SIMILARITY_THRESHOLD,
    Cluster,
    ClusterSignal,
    cluster_signals,
    confidence_score,
    cosine,
)
from scrapers.config import MissingSecretError
from scrapers.embed import vector_literal
from scrapers.http_client import HttpError, QuotaExhausted
from scrapers.llm.base import (
    REQUIRED_EMBEDDING_DIMENSIONS,
    EmbeddingClient,
    EmbeddingDimensionError,
    LLMClient,
    ProviderNotSupportedError,
)
from scrapers.llm.card_schema import validate_card
from scrapers.llm.extraction_schema import ExtractionValidationError, parse_json
from scrapers.llm.factory import embedding_client_from_env, llm_client_from_env
from scrapers.llm.prompts import synthesize_card_v1 as prompt_v1
from scrapers.store import SupabaseStore

log = logging.getLogger("scrapers.synthesize")

DEFAULT_MIN_SIGNALS = 2   # a card needs corroboration by at least two posts by default
DEFAULT_LLM_LIMIT = 10    # LLM calls per run
MAX_ATTEMPTS = 2          # first try + one retry on invalid output
#: Share of a cluster's signals already linked to one card for it to count as that card.
OVERLAP_MATCH = 0.5
#: Cosine similarity of card-text embeddings above which a new card is a duplicate of
#: an existing one. Card texts are short, LLM-normalised summaries, so true duplicates
#: score very high; 0.90 merges rewordings of one problem but keeps adjacent problems.
CARD_DUPLICATE_THRESHOLD = 0.90
SNIPPET_CHARS = 500
FREQ_MARKER = " Frequency: "
INTENT_RANK = {"Unspecified": 0, "Low": 1, "Medium": 2, "High": 3}


@dataclass
class Evidence:
    signal: ClusterSignal
    url: str
    title: str | None
    body: str | None
    problem_summary: str | None
    duct_tape: str | None
    persona: str | None
    workflow_tags: list[str] = field(default_factory=list)

    @property
    def engagement(self) -> int:
        return max(0, self.signal.score or 0) + max(0, self.signal.comment_count or 0)


@dataclass
class SynthStats:
    clusters: int = 0
    qualifying: int = 0
    created: int = 0
    merged: int = 0
    unchanged: int = 0
    rejected: int = 0
    failed_validation: int = 0
    deferred: int = 0
    llm_calls: int = 0
    errors: int = 0
    would_create: int = 0
    skipped_rejected: int = 0
    gate_passed: int = 0
    gate_failed: int = 0
    gate_rules: Counter[str] = field(default_factory=Counter)
    card_ids: list[int] = field(default_factory=list)


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _parse_vector(value: Any) -> list[float] | None:
    if value is None:
        return None
    vec = json.loads(value) if isinstance(value, str) else value
    return [float(v) for v in vec] if isinstance(vec, list) else None


def usable_vector(vec: Sequence[float] | None) -> bool:
    return (vec is not None and len(vec) == REQUIRED_EMBEDDING_DIMENSIONS
            and any(v != 0 for v in vec))


def to_evidence(row: dict[str, Any]) -> Evidence | None:
    ext = row.get("signal_extractions")
    if isinstance(ext, list):
        ext = ext[0] if ext else None
    vec = _parse_vector(row.get("embedding"))
    if not ext or not vec:
        return None
    if not usable_vector(vec):
        log.warning("signal %s: embedding is not a non-zero %d-d vector; skipped",
                    row.get("id"), REQUIRED_EMBEDDING_DIMENSIONS)
        return None
    sig = ClusterSignal(
        signal_id=int(row["id"]),
        platform=row.get("source_platform") or "other",
        embedding=vec,
        created_at=_parse_time(row.get("source_created_at")),
        score=row.get("score"),
        comment_count=row.get("comment_count"),
        economic_intent=ext.get("economic_intent") or "Unspecified",
    )
    return Evidence(sig, row.get("url") or "", row.get("title"), row.get("body"),
                    ext.get("problem_summary"), ext.get("duct_tape"), ext.get("persona"),
                    list(ext.get("workflow_tags") or []))


def strongest(items: Sequence[Evidence]) -> Evidence:
    return sorted(items, key=lambda e: (-e.engagement, e.signal.signal_id))[0]


def computed_fields(items: Sequence[Evidence], now: datetime) -> dict[str, Any]:
    """Every card field that comes from data, not from the model."""
    sigs = [e.signal for e in items]
    platforms = Counter(s.platform for s in sigs)
    top = strongest(items)
    # dominant platform; ties go to the strongest signal's platform, then by name
    dominant = sorted(platforms, key=lambda p: (-platforms[p], p != top.signal.platform, p))[0]
    dates = sorted(s.created_at for s in sigs if s.created_at)
    intent = max((s.economic_intent for s in sigs), key=lambda i: INTENT_RANK.get(i, 0))
    snippet = " ".join(f"{top.title or ''} {top.body or ''}".split())[:SNIPPET_CHARS]
    return {
        "source_platform": dominant,
        "source_url": top.url,
        "raw_content_snippet": snippet or None,
        "economic_intent": intent if intent in INTENT_RANK else "Unspecified",
        "confidence_score": confidence_score(Cluster(signals=list(sigs)), now),
        "signal_count": len(sigs),
        "platform_count": len(platforms),
        "first_seen_at": dates[0].isoformat() if dates else None,
        "last_seen_at": dates[-1].isoformat() if dates else None,
        "is_b2b_filtered": True,
    }


def frequency_sentence(items: Sequence[Evidence]) -> str:
    sigs = [e.signal for e in items]
    platforms = sorted({s.platform for s in sigs})
    dates = sorted(s.created_at for s in sigs if s.created_at)
    text = (f"{len(sigs)} post{'s' if len(sigs) != 1 else ''} across {len(platforms)} "
            f"platform{'s' if len(platforms) != 1 else ''} ({', '.join(platforms)})")
    if dates:
        text += f", {dates[0].date().isoformat()} to {dates[-1].date().isoformat()}"
    return text + "."


def trigger_context(when: str, items: Sequence[Evidence]) -> str:
    return f"{when.strip()}{FREQ_MARKER}{frequency_sentence(items)}"


def evidence_items(items: Sequence[Evidence]) -> list[dict[str, Any]]:
    ordered = sorted(items, key=lambda e: (-e.engagement, e.signal.signal_id))
    return [{
        "platform": e.signal.platform, "title": e.title, "problem_summary": e.problem_summary,
        "duct_tape": e.duct_tape, "persona": e.persona,
        "economic_intent": e.signal.economic_intent, "workflow_tags": e.workflow_tags,
        "excerpt": e.body,
    } for e in ordered]


def write_card(llm: LLMClient, items: Sequence[Evidence]) -> tuple[dict[str, Any] | None, int]:
    """(validated card JSON or None, LLM calls made). Provider errors propagate."""
    prompt = prompt_v1.build_prompt(evidence_items(items))
    for attempt in range(1, MAX_ATTEMPTS + 1):
        reply = llm.complete(prompt_v1.SYSTEM, prompt, json_mode=True)
        try:
            return validate_card(parse_json(reply)), attempt
        except ExtractionValidationError as exc:  # also CardValidationError
            log.warning("invalid card output (attempt %d): %s", attempt, exc)
    return None, MAX_ATTEMPTS


def card_text(card: dict[str, Any]) -> str:
    return f"{card['title']}\n\n{card['problem_statement']}"


def cluster_fingerprint(signal_ids: Iterable[int],
                        prompt_version: str = prompt_v1.PROMPT_VERSION) -> str:
    """Stable id of a cluster's exact signal set for one prompt version (IF-48)."""
    ids = ",".join(str(i) for i in sorted({int(s) for s in signal_ids}))
    return hashlib.sha256(f"{prompt_version}:{ids}".encode()).hexdigest()


def overlap_match(ids: set[int], links: dict[int, set[int]]) -> int | None:
    best, best_share = None, 0.0
    for card_id in sorted(links):
        share = len(ids & links[card_id]) / len(ids)
        if share > best_share:
            best, best_share = card_id, share
    return best if best_share >= OVERLAP_MATCH else None


def nearest_card(vec: Sequence[float], cards: dict[int, list[float]]) -> tuple[int | None, float]:
    best, best_sim = None, -1.0
    for card_id in sorted(cards):
        sim = cosine(vec, cards[card_id])
        if sim > best_sim:
            best, best_sim = card_id, sim
    return best, best_sim


class Synthesizer:
    def __init__(self, store: SupabaseStore, now: datetime) -> None:
        self.store, self.now = store, now
        self.links: dict[int, set[int]] = {}
        self.cards: dict[int, list[float]] = {}
        self.card_when: dict[int, str] = {}
        self.evidence: dict[int, Evidence] = {}
        self.rejected: set[str] = set()

    def load(self) -> list[Evidence]:
        items = [e for e in map(to_evidence, self.store.fetch_cluster_candidates()) if e]
        self.evidence = {e.signal.signal_id: e for e in items}
        for row in self.store.fetch_card_links():
            self.links.setdefault(int(row["card_id"]), set()).add(int(row["signal_id"]))
        for row in self.store.fetch_cards():
            card_id = int(row["id"])
            vec = _parse_vector(row.get("embedding"))
            if usable_vector(vec):
                self.cards[card_id] = vec
            self.card_when[card_id] = (row.get("trigger_context") or "").split(FREQ_MARKER)[0]
        self.rejected = self.store.fetch_rejection_fingerprints()
        return items

    def remember_rejection(self, ids: Iterable[int], reason: str, llm: LLMClient) -> None:
        fingerprint = cluster_fingerprint(ids)
        self.store.save_rejection({
            "fingerprint": fingerprint,
            "signal_ids": sorted({int(i) for i in ids}),
            "prompt_version": prompt_v1.PROMPT_VERSION,
            "reason": reason,
            "llm_model": llm.model,
        })
        self.rejected.add(fingerprint)

    def merge(self, card_id: int, ids: Iterable[int]) -> bool:
        """Link ``ids`` to the card and refresh its computed fields. False if nothing new."""
        current = self.links.setdefault(card_id, set())
        new = set(ids) - current
        if not new:
            return False
        self.store.link_card_signals(card_id, new)
        current |= new
        items = [self.evidence[i] for i in sorted(current) if i in self.evidence]
        values = computed_fields(items, self.now)
        # keep the card's original provenance (its source_url / snippet stay stable)
        for key in ("source_platform", "source_url", "raw_content_snippet"):
            values.pop(key)
        when = self.card_when.get(card_id) or "Unspecified."
        values["trigger_context"] = trigger_context(when, items)
        values["updated_at"] = self.now.isoformat()
        self.store.update_card(card_id, values)
        return True

    def build_row(self, card: dict[str, Any], items: Sequence[Evidence],
                  llm: LLMClient) -> dict[str, Any]:
        """The opportunity_cards row for a new card, without its embedding."""
        return {
            "title": card["title"],
            "problem_statement": card["problem_statement"],
            "trigger_context": trigger_context(card["trigger_when"], items),
            "market_size": card["market_size"],
            "duct_tape_solutions": card["duct_tape_solutions"],
            "mvp_wedge": card["mvp_wedge"],
            **computed_fields(items, self.now),
            "llm_model": llm.model,
            "prompt_version": prompt_v1.PROMPT_VERSION,
        }

    def create(self, card: dict[str, Any], row: dict[str, Any], items: Sequence[Evidence],
               vec: list[float], embedder: EmbeddingClient) -> int:
        row = {**row, "embedding": vector_literal(vec),
               "embedding_model": embedder.embedding_model}
        ids = {e.signal.signal_id for e in items}
        card_id = self.store.insert_card_with_links(row, ids)
        self.links[card_id] = ids
        self.cards[card_id] = vec
        self.card_when[card_id] = card["trigger_when"]
        return card_id


def run(argv: Sequence[str] | None = None, *,
        llm_factory: Callable[[], LLMClient] = llm_client_from_env,
        embedder_factory: Callable[[], EmbeddingClient] = embedding_client_from_env,
        store_factory: Callable[[], SupabaseStore] = SupabaseStore.from_env,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        out=sys.stdout) -> int:
    parser = argparse.ArgumentParser(prog="python -m scrapers.synthesize")
    parser.add_argument("--min-signals", type=int, default=DEFAULT_MIN_SIGNALS)
    parser.add_argument("--limit", type=int, default=DEFAULT_LLM_LIMIT,
                        help="max LLM calls this run")
    parser.add_argument("--threshold", type=float, default=SIMILARITY_THRESHOLD,
                        help="cluster cosine similarity threshold")
    parser.add_argument("--dry-run", action="store_true",
                        help="cluster and report only: no LLM call, no write")
    args = parser.parse_args(argv)
    if args.min_signals < 1:
        parser.error("--min-signals must be >= 1")
    if args.limit < 0:
        parser.error("--limit must be >= 0")
    if not 0 < args.threshold <= 1:
        parser.error("--threshold must be in (0, 1]")

    try:
        store = store_factory()
        llm = None if args.dry_run else llm_factory()
        embedder = None if args.dry_run else embedder_factory()
    except (MissingSecretError, ProviderNotSupportedError, EmbeddingDimensionError) as exc:
        print(f"error: {exc}", file=out)
        return 2

    started = now()
    synth = Synthesizer(store, started)
    stats = SynthStats()
    try:
        items = synth.load()
    except HttpError as exc:
        print(f"error: could not read signals/cards (HTTP {exc.status})", file=out)
        return 1

    clusters = cluster_signals([e.signal for e in items], args.threshold)
    stats.clusters = len(clusters)
    qualifying = [c for c in clusters if len(c.signals) >= args.min_signals]
    stats.qualifying = len(qualifying)
    qualifying.sort(key=lambda c: (-confidence_score(c, started), c.signal_ids[0]))

    for cluster in qualifying:
        ids = set(cluster.signal_ids)
        evidence = [synth.evidence[i] for i in cluster.signal_ids]
        try:
            matched = overlap_match(ids, synth.links)
            if matched is not None:
                if args.dry_run:
                    stats.unchanged += int(not (ids - synth.links[matched]))
                    stats.merged += int(bool(ids - synth.links[matched]))
                elif synth.merge(matched, ids):
                    stats.merged += 1
                    stats.card_ids.append(matched)
                else:
                    stats.unchanged += 1
                continue
            if cluster_fingerprint(ids) in synth.rejected:
                stats.skipped_rejected += 1
                continue
            if args.dry_run:
                stats.would_create += 1
                continue
            if llm is None or embedder is None:  # pragma: no cover - set unless dry-run
                raise RuntimeError("LLM/embedding client missing")
            if stats.llm_calls + 1 > args.limit:
                stats.deferred += 1
                continue
            card, calls = write_card(llm, evidence)
            stats.llm_calls += calls
            if card is None:
                stats.failed_validation += 1
                synth.remember_rejection(ids, "invalid", llm)
                continue
            if not card["valid_opportunity"]:
                stats.rejected += 1
                synth.remember_rejection(ids, "rejected", llm)
                continue
            row = synth.build_row(card, evidence, llm)
            failed = check_card(row, [EvidenceText(e.title, e.body, e.signal.platform)
                                      for e in evidence])
            if failed:
                stats.gate_failed += 1
                stats.gate_rules.update(failed)
                synth.remember_rejection(ids, rejection_reason(failed), llm)
                continue
            stats.gate_passed += 1
            vec = embedder.embed([card_text(card)])[0]
            dup, sim = nearest_card(vec, synth.cards)
            if dup is not None and sim >= CARD_DUPLICATE_THRESHOLD:
                synth.merge(dup, ids)
                stats.merged += 1
                stats.card_ids.append(dup)
            else:
                stats.card_ids.append(synth.create(card, row, evidence, vec, embedder))
                stats.created += 1
        except QuotaExhausted as exc:
            stats.errors += 1
            print(f"error: LLM/embedding quota exhausted (HTTP {exc.status}); stopping — "
                  "remaining clusters are left for the next run", file=out)
            break
        except EmbeddingDimensionError as exc:
            stats.errors += 1
            print(f"error: {exc}", file=out)
            break
        except (HttpError, RuntimeError) as exc:
            stats.errors += 1
            code = exc.status if isinstance(exc, HttpError) else "n/a"
            print(f"error: provider/store request failed (HTTP {code}); stopping", file=out)
            break

    mode = "dry-run" if args.dry_run else "stored"
    model = f"{llm.provider}/{llm.model}" if llm else "none"
    print(
        f"synthesize mode={mode} model={model} prompt={prompt_v1.PROMPT_VERSION} "
        f"signals={len(items)} clusters={stats.clusters} qualifying={stats.qualifying} "
        f"created={stats.created} merged={stats.merged} unchanged={stats.unchanged} "
        f"rejected={stats.rejected} failed={stats.failed_validation} "
        f"skipped_rejected={stats.skipped_rejected} "
        f"deferred={stats.deferred} would_create={stats.would_create} "
        f"llm_calls={stats.llm_calls} errors={stats.errors}"
        + (f" card_ids={','.join(map(str, stats.card_ids))}" if stats.card_ids else ""),
        file=out,
    )
    if not args.dry_run:
        print("quality_gate "
              f"passed={stats.gate_passed} failed={stats.gate_failed} "
              + " ".join(f"{rule}={stats.gate_rules[rule]}" for rule in QUALITY_RULES),
              file=out)
    return 0 if stats.errors == 0 else 1


def main() -> None:  # pragma: no cover - thin wrapper
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    raise SystemExit(run())


if __name__ == "__main__":  # pragma: no cover
    main()
