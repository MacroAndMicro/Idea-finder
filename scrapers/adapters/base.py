"""SourceAdapter: the one interface every ingestion source implements."""

from __future__ import annotations

import abc
from collections.abc import Iterator
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
