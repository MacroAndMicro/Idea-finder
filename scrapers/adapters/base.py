"""SourceAdapter: the one interface every ingestion source implements."""

from __future__ import annotations

import abc
from collections.abc import Iterable, Iterator, Sequence
from datetime import UTC, datetime, timedelta

from scrapers.http_client import HttpClient
from scrapers.models import RawSignal


def rolling_window_start(since: datetime, now: datetime, lookback_days: int) -> datetime:
    """The earlier of ``since`` and now - ``lookback_days`` (IF-93, IF-94).

    A ~4h run window is too short for signals that need time to earn reactions, votes or
    answers; ``lookback_days <= 0`` disables the rolling window (plain ``since``).
    """
    if since.tzinfo is None:
        since = since.replace(tzinfo=UTC)
    if lookback_days <= 0:
        return since
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    return min(since, now - timedelta(days=lookback_days))


def interleave(streams: Iterable[Iterator[RawSignal]]) -> Iterator[RawSignal]:
    """Round-robin over lazy streams until all are exhausted, so one stream cannot fill a
    shared ``--limit`` on its own (IF-93, IF-94)."""
    active = list(streams)
    while active:
        for stream in list(active):
            try:
                yield next(stream)
            except StopIteration:
                active.remove(stream)


class SourceAdapter(abc.ABC):
    #: value written to raw_signals.source_platform
    platform: str

    def __init__(self, client: HttpClient | None = None, *, max_pages: int = 5) -> None:
        self.client = client or HttpClient()
        self.max_pages = max_pages

    @abc.abstractmethod
    def fetch(self, query: str, since: datetime) -> Iterator[RawSignal]:
        """Yield normalized signals matching ``query`` created after ``since`` (UTC)."""

    def fetch_all(self, queries: Sequence[str], since: datetime) -> Iterator[RawSignal]:
        """Signals for every query, in order. Adapters with several streams (e.g. GitHub
        issues + discussions) override this to interleave them under one ``--limit``."""
        for query in queries:
            yield from self.fetch(query, since)
