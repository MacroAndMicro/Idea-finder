"""IF-62: deterministic card quality gate (pure; fixtures only, no network)."""

from __future__ import annotations

import pytest

from scrapers.card_quality import (
    RULES,
    EvidenceText,
    check_card,
    claimed_counts,
    rejection_reason,
    sentence_count,
)

EVIDENCE = [
    EvidenceText("Merging CSV exports weekly", "We   merge Stripe CSV exports by hand.", "github"),
    EvidenceText("Same pain", "Our ops team pastes CSVs every Monday.", "hackernews"),
]


def good_card(**over):
    card = {
        "title": "Merging weekly CSV exports",
        "problem_statement": "Ops teams merge CSV exports by hand, e.g. Stripe payouts. "
                             "It costs hours every week.",
        "trigger_context": "Every Monday reporting run. Frequency: 2 posts across 2 "
                           "platforms (github, hackernews), 2026-11-01 to 2026-11-10.",
        "duct_tape_solutions": "Manual CSV merges in spreadsheets",
        "mvp_wedge": "A CSV merge service with a Stripe connector.",
        "economic_intent": "Medium",
        "confidence_score": 42,
        "raw_content_snippet": "merging csv exports weekly we merge stripe CSV exports",
    }
    return {**card, **over}


def test_good_card_passes():
    assert check_card(good_card(), EVIDENCE) == []


@pytest.mark.parametrize(("rule", "over"), [
    ("trigger_counts", {"trigger_context": "Reported in 15 GitHub issues. Frequency: 2 posts "
                                           "across 2 platforms (github, hackernews)."}),
    ("trigger_counts", {"trigger_context": "Seen on three platforms. Frequency: 2 posts."}),
    ("snippet_in_evidence", {"raw_content_snippet": "we pay $5k a month for this"}),
    ("snippet_in_evidence", {"raw_content_snippet": None}),
    ("problem_statement_sentences", {"problem_statement": "One. Two. Three."}),
    ("problem_statement_sentences", {"problem_statement": "   "}),
    ("economic_intent_enum", {"economic_intent": "Very High"}),
    ("mvp_wedge_nonempty", {"mvp_wedge": " "}),
    ("duct_tape_nonempty", {"duct_tape_solutions": ""}),
    ("confidence_range", {"confidence_score": 0}),
    ("confidence_range", {"confidence_score": 101}),
    ("confidence_range", {"confidence_score": 55.5}),
    ("confidence_range", {"confidence_score": True}),
])
def test_each_rule_fails_alone(rule, over):
    assert check_card(good_card(**over), EVIDENCE) == [rule]


def test_every_rule_has_a_failing_case():
    covered = {r for r, _ in test_each_rule_fails_alone.pytestmark[0].args[1]}
    assert covered == set(RULES)


def test_claimed_counts_parsing():
    assert claimed_counts("2 posts across 2 platforms (github, hn), 2026-11-01 to 2026-11-10."
                          ) == [(2, "signals"), (2, "platforms")]
    assert claimed_counts("15 separate GitHub issues on two distinct sources") == [
        (15, "signals"), (2, "platforms")]
    assert claimed_counts("one of the posts mentions 12 users and 3 teams") == []
    assert claimed_counts("") == []


def test_sentence_count_handles_abbreviations():
    assert sentence_count("Teams merge CSVs, e.g. Stripe exports. It costs hours!") == 2
    assert sentence_count("No terminal punctuation") == 1
    assert sentence_count("A. B. C.") == 3


def test_rejection_reason_format():
    assert rejection_reason(["trigger_counts", "confidence_range"]) == \
        "quality:trigger_counts,confidence_range"
