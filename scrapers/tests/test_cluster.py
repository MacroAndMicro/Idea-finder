from __future__ import annotations

import math
import random
from datetime import UTC, datetime, timedelta

import pytest

from scrapers.cluster import (
    SIMILARITY_THRESHOLD,
    Cluster,
    ClusterSignal,
    cluster_signals,
    confidence_score,
    cosine,
)

NOW = datetime(2026, 11, 17, tzinfo=UTC)
DIM = 8


def axis(i: int, noise: float = 0.0, seed: int = 0) -> list[float]:
    rng = random.Random(seed)
    v = [rng.uniform(-noise, noise) for _ in range(DIM)]
    v[i] += 1.0
    return v


def s(sid, vec, platform="hackernews", **kw) -> ClusterSignal:
    return ClusterSignal(sid, platform, vec, **kw)


def test_cosine_basics():
    assert cosine([1, 0], [1, 0]) == pytest.approx(1)
    assert cosine([1, 0], [0, 1]) == pytest.approx(0)
    assert cosine([0, 0], [1, 0]) == 0
    with pytest.raises(ValueError):
        cosine([1], [1, 2])


def test_groups_similar_and_separates_distinct():
    sigs = [s(1, axis(0, .05, 1)), s(2, axis(1, .05, 2)), s(3, axis(0, .05, 3)),
            s(4, axis(1, .05, 4)), s(5, axis(2, .05, 5))]
    clusters = cluster_signals(sigs, dimensions=DIM)
    assert [c.signal_ids for c in clusters] == [[1, 3], [2, 4], [5]]


def test_deterministic_regardless_of_input_order():
    sigs = [s(i, axis(i % 3, .1, i)) for i in range(1, 20)]
    a = cluster_signals(sigs, dimensions=DIM)
    shuffled = sigs[:]
    random.Random(42).shuffle(shuffled)
    b = cluster_signals(shuffled, dimensions=DIM)
    assert [c.signal_ids for c in a] == [c.signal_ids for c in b]


def test_threshold_is_configurable():
    v1, v2 = [1.0, 0.0], [math.cos(0.5), math.sin(0.5)]  # cos ≈ 0.878
    sigs = [s(1, v1), s(2, v2)]
    assert len(cluster_signals(sigs, 0.85, dimensions=2)) == 1
    assert len(cluster_signals(sigs, 0.95, dimensions=2)) == 2
    assert 0 < SIMILARITY_THRESHOLD < 1
    with pytest.raises(ValueError):
        cluster_signals(sigs, 0, dimensions=2)


def test_filters_non_pain_and_consumer():
    sigs = [s(1, axis(0)), s(2, axis(0), is_pain_point=False), s(3, axis(0), is_b2b=False)]
    assert [c.signal_ids for c in cluster_signals(sigs, dimensions=DIM)] == [[1]]


def test_rejects_wrong_dimensions_and_zero_vectors():
    with pytest.raises(ValueError, match="expected 1536"):
        cluster_signals([s(1, [1.0, 0.0])])
    with pytest.raises(ValueError):
        cluster_signals([s(1, [0.0] * DIM)], dimensions=DIM)


def make_cluster(sigs) -> Cluster:
    c = Cluster()
    for sig in sigs:
        c.add(sig, [1.0])
    return c


def test_confidence_bounds():
    assert confidence_score(Cluster(), NOW) == 1
    weak = make_cluster([s(1, [1.0])])
    assert 1 <= confidence_score(weak, NOW) <= 15
    strong = make_cluster([
        s(i, [1.0], platform=p, created_at=NOW - timedelta(days=2), score=100,
          comment_count=20, economic_intent="High")
        for i, p in enumerate(["hackernews", "github", "stackexchange"] * 4)
    ])
    assert confidence_score(strong, NOW) == 100


def test_confidence_single_signal_formula():
    c = make_cluster([s(1, [1.0], created_at=NOW - timedelta(days=1), score=9,
                        economic_intent="Medium")])
    expected = (30 * math.log2(2) / math.log2(11) + 0 + 20
                + 15 * math.log10(10) / math.log10(501) + 10 * 0.6)
    assert confidence_score(c, NOW) == round(expected)


@pytest.mark.parametrize("factor", ["spread", "recency", "engagement", "intent", "volume"])
def test_each_factor_raises_score(factor):
    base = dict(platform="hackernews", created_at=NOW - timedelta(days=90), score=0,
                comment_count=0, economic_intent="Unspecified")
    low = make_cluster([s(1, [1.0], **base), s(2, [1.0], **base)])
    tweak = dict(base)
    extra = []
    if factor == "spread":
        tweak["platform"] = "github"
    elif factor == "recency":
        tweak["created_at"] = NOW - timedelta(days=3)
    elif factor == "engagement":
        tweak["score"] = 50
    elif factor == "intent":
        tweak["economic_intent"] = "High"
    else:
        extra = [s(3, [1.0], **base), s(4, [1.0], **base)]
    high = make_cluster([s(1, [1.0], **base), s(2, [1.0], **tweak), *extra])
    assert confidence_score(high, NOW) > confidence_score(low, NOW)
