from __future__ import annotations

import pytest

from scrapers import prioritize as p


def sig(i, title="", body="", **kw):
    return {"id": i, "title": title, "body": body, **kw}


@pytest.mark.parametrize("title,body,skip", [
    ("", None, True),
    ("short", "   ", True),
    ("x" * (p.MIN_TEXT_CHARS - 1), "", True),
    ("x" * p.MIN_TEXT_CHARS, "", False),
    ("Q", "y" * 60, False),
])
def test_skip_rule(title, body, skip):
    assert p.should_skip(sig(1, title, body)) is skip


def test_pain_and_b2b_terms_raise_priority():
    base = sig(1, "Question about something", "I was reading about this topic today " * 3)
    pain = sig(2, "Broken export, how do I fix it?",
               "Our team uses a manual CSV workaround in production every week " * 3)
    assert p.priority_score(pain) > p.priority_score(base)


def test_engagement_and_length_raise_priority_and_are_capped():
    text = "Deploy pipeline fails with a workaround needed " * 2
    low = sig(1, "t", text, score=0, comment_count=0)
    high = sig(2, "t", text, score=50, comment_count=30)
    assert p.priority_score(high) > p.priority_score(low)
    assert p.priority_score(sig(3, "t", "a" * 100_000)) == p.priority_score(
        sig(4, "t", "a" * p.LENGTH_SATURATION))
    many = sig(5, "t", " ".join(p.PAIN_PHRASES))
    assert p.priority_score(many) <= (p.PAIN_WEIGHT * p.MAX_PAIN_HITS
                                      + p.B2B_WEIGHT * p.MAX_B2B_HITS + p.LENGTH_WEIGHT)


def test_bad_engagement_values_are_zero():
    a = sig(1, "t" * 50, score=-30, comment_count=None)
    b = sig(2, "t" * 50, score="n/a", comment_count=0)
    c = sig(3, "t" * 50)
    assert p.priority_score(a) == p.priority_score(b) == p.priority_score(c)


def test_tags_count_as_b2b_terms():
    plain = sig(1, "t" * 50)
    tagged = sig(2, "t" * 50, tags=["DevOps", "api"])
    assert p.priority_score(tagged) == p.priority_score(plain) + 2 * p.B2B_WEIGHT


def test_plan_is_deterministic_and_does_not_mutate():
    rows = [sig(3, "t" * 50), sig(1, "t" * 50), sig(2, ""),
            sig(4, "workaround for broken api in production", "x" * 200)]
    before = [dict(r) for r in rows]
    ranked, skipped = p.plan(rows)
    assert [r["id"] for r in ranked] == [4, 1, 3]  # best first, ties by id
    assert [r["id"] for r in skipped] == [2]
    assert rows == before
    assert p.plan(reversed(rows))[0] == ranked
