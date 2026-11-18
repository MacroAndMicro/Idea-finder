"""IF-63: the clustering threshold separates labelled same-pain / different-pain pairs,
and ``python -m scrapers.cluster --report`` stays read-only and well-formed.

Embeddings come from a bag-of-words built on the hash-based ``FakeEmbeddingClient``
(one fake vector per content word, summed): no network, no provider. It is a stand-in
that makes paraphrases close and adjacent problems far, so the test checks the
threshold *mechanics*; the real-model numbers live in scrapers/README.md.
"""

from __future__ import annotations

import io
import json
import math
import re
from functools import cache

import pytest

from scrapers import cluster
from scrapers.cluster import SIMILARITY_THRESHOLD, ClusterSignal, cluster_signals, cosine
from scrapers.config import MissingSecretError
from scrapers.llm.fake import FakeEmbeddingClient
from scrapers.tests.helpers import FIXTURES

PAIRS = json.loads((FIXTURES / "cluster" / "labelled_pairs.json").read_text())
STOP = {"the", "and", "our", "for", "into", "from", "every", "each", "because", "are", "can",
        "does", "not", "nobody", "until", "get", "gets", "too", "both", "after", "across",
        "during", "keeps", "never", "them", "their", "this", "that", "with", "over", "under"}
_FAKE = FakeEmbeddingClient()


@cache
def _word(word: str) -> tuple[float, ...]:
    return tuple(_FAKE.embed([word])[0])


def embed(text: str) -> list[float]:
    words = {w for w in re.findall(r"[a-z]{3,}", text.lower()) if w not in STOP}
    vec = [0.0] * 1536
    for w in sorted(words):
        vec = [a + b for a, b in zip(vec, _word(w), strict=True)]
    norm = math.sqrt(sum(x * x for x in vec))
    return [x / norm for x in vec]


def test_fixture_has_enough_labelled_pairs():
    assert len(PAIRS["same"]) >= 10 and len(PAIRS["different"]) >= 10


def test_threshold_separates_same_from_different_pain():
    same = [cosine(embed(a), embed(b)) for a, b in PAIRS["same"]]
    diff = [cosine(embed(a), embed(b)) for a, b in PAIRS["different"]]
    assert min(same) >= SIMILARITY_THRESHOLD > max(diff), (min(same), max(diff))


@pytest.mark.parametrize("label", ["same", "different"])
def test_pairs_cluster_as_labelled(label):
    for i, (a, b) in enumerate(PAIRS[label]):
        sigs = [ClusterSignal(2 * i, "github", embed(a)),
                ClusterSignal(2 * i + 1, "github", embed(b))]
        sizes = [len(c.signals) for c in cluster_signals(sigs)]
        assert sizes == ([2] if label == "same" else [1, 1]), (label, a, b)


def _sig(sid, axis_weights):
    v = [0.0] * 1536
    for axis, w in axis_weights.items():
        v[axis] = w
    return ClusterSignal(sid, "github", v)


def test_sweep_and_report_shape():
    # 1 & 2 nearly identical, 3 at ~0.75 to them, 4 orthogonal
    sigs = [_sig(1, {0: 1.0}), _sig(2, {0: 1.0, 1: 0.05}), _sig(3, {0: 0.75, 2: 0.66}),
            _sig(4, {5: 1.0})]
    sweep = {r["threshold"]: r for r in cluster.threshold_sweep(sigs)}
    assert list(sweep) == [0.7, 0.72, 0.74, 0.76, 0.78, 0.8, 0.82, 0.84, 0.86, 0.88, 0.9]
    assert sweep[0.7]["sizes"] == [3, 1] and sweep[0.7]["qualifying"] == 1
    assert sweep[0.9]["sizes"] == [2, 1, 1]
    assert len(cluster.pairwise_similarities(sigs)) == 6
    out = io.StringIO()
    assert cluster.run(["--report"], loader=lambda: sigs, out=out) == 0
    text = out.getvalue()
    assert text.startswith("cluster-report signals=4 pairs=6 current_threshold=0.82")
    assert "threshold=0.70 clusters=2 qualifying=1 sizes=3,1" in text
    assert "similarity min=" in text


def test_report_handles_empty_and_missing_secret():
    out = io.StringIO()
    assert cluster.run(["--report"], loader=list, out=out) == 0
    assert "signals=0 pairs=0" in out.getvalue() and "similarity" not in out.getvalue()

    def missing():
        raise MissingSecretError("SUPABASE_URL")
    out = io.StringIO()
    assert cluster.run(["--report"], loader=missing, out=out) == 2
    assert "missing SUPABASE_URL" in out.getvalue()
