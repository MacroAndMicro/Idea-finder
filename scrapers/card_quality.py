"""Deterministic quality gate for synthesized Opportunity Cards (IF-62).

Pure functions, no I/O, no LLM. ``synthesize`` runs :func:`check_card` on the row it is
about to insert; any failed rule keeps the card out of ``opportunity_cards`` and the
cluster is remembered in ``synthesis_rejections`` with reason
``quality:<rule>[,<rule>…]`` so it does not spend LLM budget again until its signals
(or the prompt) change.

Rules (names are what gets recorded and printed):

``trigger_counts``
    Every number in ``trigger_context`` that claims a count of posts / mentions /
    signals / threads / reports / complaints / issues / questions must equal the
    cluster's signal count, and every number that claims platforms / sources / sites
    must equal its distinct platform count. Digits and the words one…twenty count.
``snippet_in_evidence``
    ``raw_content_snippet`` (whitespace and case normalised) appears in at least one
    member signal's ``title + body``.
``problem_statement_sentences``
    ``problem_statement`` is 1–2 sentences.
``economic_intent_enum``
    ``economic_intent`` is High / Medium / Low / Unspecified.
``mvp_wedge_nonempty`` / ``duct_tape_nonempty``
    ``mvp_wedge`` and ``duct_tape_solutions`` are non-blank.
``confidence_range``
    ``confidence_score`` is an integer within 1–100.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

ECONOMIC_INTENTS = frozenset({"High", "Medium", "Low", "Unspecified"})
REASON_PREFIX = "quality:"

RULES = (
    "trigger_counts",
    "snippet_in_evidence",
    "problem_statement_sentences",
    "economic_intent_enum",
    "mvp_wedge_nonempty",
    "duct_tape_nonempty",
    "confidence_range",
)

_NUMBER_WORDS = {w: i for i, w in enumerate((
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
    "eighteen", "nineteen", "twenty"))}
_SIGNAL_NOUNS = ("posts?|mentions?|signals?|threads?|reports?|complaints?|issues?|"
                 "questions?|discussions?")
_PLATFORM_NOUNS = "platforms?|sources?|sites?|communities"
_NUM = r"(\d+|" + "|".join(_NUMBER_WORDS) + r")"
# "3 posts", "3 separate GitHub issues", "two distinct platforms": up to 3 words between.
# Words that end a count phrase ("one of the posts" is not a claim of one post).
_STOP = r"(?:of|the|these|those|their|its|in|on|at|for|with|from|and|or|to|by|per|a|an)\b"
_COUNT_RE = re.compile(
    r"\b" + _NUM + r"(?:[\s-]+(?!" + _STOP + r")[A-Za-z][\w.+#-]*){0,3}?[\s-]+("
    + _SIGNAL_NOUNS + "|" + _PLATFORM_NOUNS + r")\b",
    re.IGNORECASE,
)
_PLATFORM_RE = re.compile(r"^(?:" + _PLATFORM_NOUNS + r")$", re.IGNORECASE)
_SENTENCE_END = re.compile(r"[.!?]+(?:[\"')\]]+)?(?=\s+|$)")
_ABBREVIATIONS = ("e.g.", "i.e.", "etc.", "vs.", "approx.", "incl.")


@dataclass(frozen=True)
class EvidenceText:
    """The parts of one member signal the gate needs."""

    title: str | None
    body: str | None
    platform: str


def _norm(text: str | None) -> str:
    return " ".join((text or "").split()).casefold()


def _to_int(token: str) -> int:
    return int(token) if token.isdigit() else _NUMBER_WORDS[token.casefold()]


def claimed_counts(text: str) -> list[tuple[int, str]]:
    """(number, "signals" | "platforms") for every count claim in ``text``."""
    claims = []
    for match in _COUNT_RE.finditer(text or ""):
        kind = "platforms" if _PLATFORM_RE.match(match.group(2)) else "signals"
        claims.append((_to_int(match.group(1)), kind))
    return claims


def sentence_count(text: str) -> int:
    cleaned = " ".join((text or "").split())
    for abbr in _ABBREVIATIONS:
        cleaned = re.sub(re.escape(abbr), abbr.replace(".", ""), cleaned, flags=re.IGNORECASE)
    parts = [p for p in _SENTENCE_END.split(cleaned) if p.strip(" \"')]")]
    return len(parts)


def _blank(value: Any) -> bool:
    return not isinstance(value, str) or not value.strip()


def check_card(card: Mapping[str, Any], evidence: Sequence[EvidenceText]) -> list[str]:
    """Names of the rules ``card`` (an ``opportunity_cards`` row) fails; [] = passes."""
    failed: list[str] = []
    signals, platforms = len(evidence), len({e.platform for e in evidence})
    for number, kind in claimed_counts(str(card.get("trigger_context") or "")):
        if number != (platforms if kind == "platforms" else signals):
            failed.append("trigger_counts")
            break

    snippet = _norm(card.get("raw_content_snippet"))
    haystacks = [_norm(f"{e.title or ''} {e.body or ''}") for e in evidence]
    if not snippet or not any(snippet in h for h in haystacks):
        failed.append("snippet_in_evidence")

    problem = card.get("problem_statement")
    if _blank(problem) or not 1 <= sentence_count(problem) <= 2:
        failed.append("problem_statement_sentences")

    if card.get("economic_intent") not in ECONOMIC_INTENTS:
        failed.append("economic_intent_enum")
    if _blank(card.get("mvp_wedge")):
        failed.append("mvp_wedge_nonempty")
    if _blank(card.get("duct_tape_solutions")):
        failed.append("duct_tape_nonempty")

    score = card.get("confidence_score")
    if isinstance(score, bool) or not isinstance(score, int) or not 1 <= score <= 100:
        failed.append("confidence_range")
    return failed


def rejection_reason(failed: Sequence[str]) -> str:
    """Value stored in ``synthesis_rejections.reason`` for a gate failure."""
    return REASON_PREFIX + ",".join(failed)
