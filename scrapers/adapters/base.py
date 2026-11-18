"""SourceAdapter: the one interface every ingestion source implements."""

from __future__ import annotations

import abc
from collections.abc import Iterator, Sequence
from datetime import datetime

from scrapers.http_client import HttpClient
from scrapers.models import RawSignal


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
