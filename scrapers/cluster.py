"""Group extracted B2B pain-point signals and score how well-validated each group is.

Pure functions only: no I/O, no DB writes. Output is deterministic for a given input
(signals are processed in ascending ``signal_id`` order regardless of input order).

Clustering — greedy centroid ("leader") clustering on cosine similarity:
each signal joins the existing cluster whose centroid is most similar, if that
similarity is >= ``threshold`` (default ``SIMILARITY_THRESHOLD``); otherwise it
starts a new cluster. Ties go to the older cluster. Centroids are the mean of
member vectors. Centroid linkage avoids the chaining that single-linkage causes.

Confidence (1–100) — see ``confidence_score`` and scrapers/README.md.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta

#: Cosine similarity needed to join a cluster. 0.82 keeps paraphrases of the same
#: complaint together while separating adjacent problems in the same tool/domain.
SIMILARITY_THRESHOLD = 0.82
EMBEDDING_DIMENSIONS = 1536

# Confidence weights (sum = 100) and saturation points.
W_VOLUME, W_SPREAD, W_RECENCY, W_ENGAGEMENT, W_INTENT = 30, 25, 20, 15, 10
VOLUME_SATURATION = 10        # signals
SPREAD_SATURATION = 3         # distinct platforms
RECENT_WINDOW = timedelta(days=30)
ENGAGEMENT_SATURATION = 500   # summed score + comments
INTENT_WEIGHT = {"High": 1.0, "Medium": 0.6, "Low": 0.3, "Unspecified": 0.0}


@dataclass(frozen=True)
class ClusterSignal:
    signal_id: int
    platform: str
    embedding: Sequence[float]
    created_at: datetime | None = None
    score: int | None = None
    comment_count: int | None = None
    economic_intent: str = "Unspecified"
    is_pain_point: bool = True
    is_b2b: bool = True


@dataclass
class Cluster:
    signals: list[ClusterSignal] = field(default_factory=list)
    centroid: list[float] = field(default_factory=list)

    @property
    def signal_ids(self) -> list[int]:
        return [s.signal_id for s in self.signals]

    @property
    def platforms(self) -> set[str]:
        return {s.platform for s in self.signals}

    def add(self, signal: ClusterSignal, vector: list[float]) -> None:
        n = len(self.signals)
        self.centroid = vector[:] if n == 0 else [
            (c * n + v) / (n + 1) for c, v in zip(self.centroid, vector, strict=True)
        ]
        self.signals.append(signal)


def _normalize(vec: Sequence[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0:
        raise ValueError("zero-length embedding")
    return [x / norm for x in vec]


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b):
        raise ValueError(f"dimension mismatch: {len(a)} != {len(b)}")
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return sum(x * y for x, y in zip(a, b, strict=True)) / (na * nb)


def cluster_signals(
    signals: Iterable[ClusterSignal],
    threshold: float = SIMILARITY_THRESHOLD,
    *,
    dimensions: int | None = EMBEDDING_DIMENSIONS,
) -> list[Cluster]:
    """Cluster pain-point B2B signals; others are ignored. Clusters ordered by first id."""
    if not 0 < threshold <= 1:
        raise ValueError("threshold must be in (0, 1]")
    eligible = sorted(
        (s for s in signals if s.is_pain_point and s.is_b2b), key=lambda s: s.signal_id
    )
    clusters: list[Cluster] = []
    for signal in eligible:
        if dimensions is not None and len(signal.embedding) != dimensions:
            raise ValueError(
                f"signal {signal.signal_id}: expected {dimensions} dims, "
                f"got {len(signal.embedding)}"
            )
        vec = _normalize(signal.embedding)
        best, best_sim = None, threshold
        for cluster in clusters:
            sim = cosine(vec, cluster.centroid)
            if sim >= best_sim and (best is None or sim > best_sim):
                best, best_sim = cluster, sim
        if best is None:
            best = Cluster()
            clusters.append(best)
        best.add(signal, vec)
    return clusters


def confidence_score(cluster: Cluster, now: datetime) -> int:
    """Score 1–100 from volume, source spread, recency, engagement and economic intent.

    volume     = 30 * min(1, log2(1+n) / log2(1+10))
    spread     = 25 * min(1, (platforms-1) / (3-1))
    recency    = 20 * share of signals created within 30 days of ``now``
                 (signals with unknown dates count as not recent)
    engagement = 15 * min(1, log10(1+sum(score+comments)) / log10(1+500))
    intent     = 10 * max intent weight (High 1, Medium .6, Low .3, Unspecified 0)
    """
    sigs = cluster.signals
    n = len(sigs)
    if n == 0:
        return 1
    volume = min(1.0, math.log2(1 + n) / math.log2(1 + VOLUME_SATURATION))
    spread = min(1.0, (len(cluster.platforms) - 1) / (SPREAD_SATURATION - 1))
    recent = sum(1 for s in sigs if s.created_at and now - s.created_at <= RECENT_WINDOW)
    recency = recent / n
    engagement_total = sum(max(0, s.score or 0) + max(0, s.comment_count or 0) for s in sigs)
    engagement = min(1.0, math.log10(1 + engagement_total) / math.log10(1 + ENGAGEMENT_SATURATION))
    intent = max(INTENT_WEIGHT.get(s.economic_intent, 0.0) for s in sigs)
    raw = (W_VOLUME * volume + W_SPREAD * spread + W_RECENCY * recency
           + W_ENGAGEMENT * engagement + W_INTENT * intent)
    return max(1, min(100, round(raw)))
