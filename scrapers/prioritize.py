"""Cheap, deterministic, non-LLM ranking of unprocessed raw_signals (IF-50).

With a tiny daily LLM budget, ``scrapers.extract`` should spend requests on the posts
most likely to be B2B / developer pain, not on the oldest rows. Two rules, all
constants here:

* **Skip rule** — a signal whose stripped title + body is shorter than
  ``MIN_TEXT_CHARS`` has nothing to classify. ``extract`` marks it processed
  (``processed_at`` set, *no* ``signal_extractions`` row = "skipped by pre-filter") so it
  never consumes a request. Nothing is deleted from ``raw_signals``.
* **Priority score** (higher first; ties → lower id first, so it is deterministic):

  ====================  =====================================================
  engagement            ``ENGAGEMENT_WEIGHT * log10(1 + score + 2*comments)``
                        (negative scores count as 0; comments weigh double —
                        a reply thread signals a shared problem)
  body length           ``LENGTH_WEIGHT * min(1, len(body) / LENGTH_SATURATION)``
  pain phrases          ``PAIN_WEIGHT`` per distinct phrase in title/body
                        (``workaround``, ``broken``, ``how do i`` …), max
                        ``MAX_PAIN_HITS``
  B2B terms             ``B2B_WEIGHT`` per distinct term in title/body/tags
                        (``team``, ``production``, ``api``, ``invoice`` …),
                        max ``MAX_B2B_HITS``
  ====================  =====================================================

Pure functions, stdlib only, no I/O.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping
from typing import Any

MIN_TEXT_CHARS = 40

ENGAGEMENT_WEIGHT = 2.0
LENGTH_WEIGHT = 2.0
LENGTH_SATURATION = 1500
PAIN_WEIGHT = 1.5
MAX_PAIN_HITS = 4
B2B_WEIGHT = 1.0
MAX_B2B_HITS = 3

PAIN_PHRASES: tuple[str, ...] = (
    "workaround", "work around", "broken", "doesn't work", "does not work",
    "how do i", "how can i", "is there a tool", "is there a way", "manually",
    "spreadsheet", "csv", "we pay", "paying for", "too expensive", "pain",
    "frustrat", "keeps failing", "no way to", "missing feature", "feature request",
    "hack", "script to", "time-consuming", "wasted hours",
)
B2B_TERMS: tuple[str, ...] = (
    "team", "teams", "company", "customer", "customers", "client", "clients",
    "production", "prod", "enterprise", "saas", "api", "integration", "pipeline",
    "deploy", "ci", "invoice", "billing", "crm", "erp", "compliance", "audit",
    "on-call", "devops", "sysadmin", "workflow", "dashboard", "report",
)

_WORD_RE = re.compile(r"[a-z0-9][a-z0-9\-]*")


def _text(signal: Mapping[str, Any]) -> tuple[str, str]:
    return (signal.get("title") or "").strip(), (signal.get("body") or "").strip()


def should_skip(signal: Mapping[str, Any]) -> bool:
    title, body = _text(signal)
    return len(title) + len(body) < MIN_TEXT_CHARS


def _nonneg(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def priority_score(signal: Mapping[str, Any]) -> float:
    title, body = _text(signal)
    text = f"{title}\n{body}".lower()
    words = set(_WORD_RE.findall(text))
    words |= {str(t).strip().lower() for t in (signal.get("tags") or []) if t}
    engagement = _nonneg(signal.get("score")) + 2 * _nonneg(signal.get("comment_count"))
    pain_hits = sum(1 for p in PAIN_PHRASES if p in text)
    b2b_hits = sum(1 for t in B2B_TERMS if t in words)
    return (
        ENGAGEMENT_WEIGHT * math.log10(1 + engagement)
        + LENGTH_WEIGHT * min(1.0, len(body) / LENGTH_SATURATION)
        + PAIN_WEIGHT * min(pain_hits, MAX_PAIN_HITS)
        + B2B_WEIGHT * min(b2b_hits, MAX_B2B_HITS)
    )


def plan(signals: Iterable[Mapping[str, Any]]
         ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(ranked signals to extract, best first; signals to skip). Input is not mutated."""
    ranked: list[tuple[float, int, dict[str, Any]]] = []
    skipped: list[dict[str, Any]] = []
    for sig in signals:
        row = dict(sig)
        if should_skip(row):
            skipped.append(row)
        else:
            ranked.append((-priority_score(row), int(row["id"]), row))
    ranked.sort(key=lambda t: (t[0], t[1]))
    return [r for _, _, r in ranked], skipped
