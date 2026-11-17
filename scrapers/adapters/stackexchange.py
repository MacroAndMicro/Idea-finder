"""Stack Exchange via the official API v2.3 (requires STACKEXCHANGE_KEY).

Honors the response ``backoff`` field (no request to the same method before it
elapses) and stops when ``quota_remaining`` drops below a safety floor.
Responses are always gzip-compressed; the shared client decodes them.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator, Sequence
from datetime import datetime

from scrapers import config
from scrapers.adapters.base import SourceAdapter
from scrapers.http_client import HttpClient
from scrapers.models import RawSignal, from_unix, hash_author, html_to_text

log = logging.getLogger(__name__)

SEARCH_URL = "https://api.stackexchange.com/2.3/search/advanced"
DEFAULT_SITES = ("stackoverflow", "serverfault", "superuser")
PAGE_SIZE = 100
QUOTA_FLOOR = 50  # keep headroom for other jobs sharing the daily key quota
MIN_INTERVAL_SECONDS = 0.5  # API asks for < 30 req/s; we stay well under


class StackExchangeAdapter(SourceAdapter):
    platform = "stackexchange"

    def __init__(
        self,
        key: str | None,
        client: HttpClient | None = None,
        *,
        sites: Sequence[str] = DEFAULT_SITES,
        max_pages: int = 3,
        quota_floor: int = QUOTA_FLOOR,
    ) -> None:
        super().__init__(client or HttpClient(min_interval=MIN_INTERVAL_SECONDS),
                         max_pages=max_pages)
        self._key = key
        self.sites = tuple(sites)
        self.quota_floor = quota_floor
        self.quota_remaining: int | None = None

    @classmethod
    def from_env(cls, **kwargs) -> StackExchangeAdapter:
        sites = config.get_env("STACKEXCHANGE_SITES")
        if sites:
            kwargs.setdefault("sites", [s.strip() for s in sites.split(",") if s.strip()])
        return cls(config.get_env("STACKEXCHANGE_KEY"), **kwargs)

    def fetch(self, query: str, since: datetime) -> Iterator[RawSignal]:
        if not self._key:
            log.warning("STACKEXCHANGE_KEY is not set; skipping Stack Exchange ingestion")
            return
        for site in self.sites:
            for page in range(1, self.max_pages + 1):
                if self.quota_remaining is not None and self.quota_remaining < self.quota_floor:
                    log.warning("Stack Exchange quota low (%s); stopping", self.quota_remaining)
                    return
                data = self.client.get(
                    SEARCH_URL,
                    {
                        "q": query,
                        "site": site,
                        "fromdate": int(since.timestamp()),
                        "sort": "creation",
                        "order": "desc",
                        "page": page,
                        "pagesize": PAGE_SIZE,
                        "filter": "withbody",
                        "key": self._key,
                    },
                ).json()
                if "quota_remaining" in data:
                    self.quota_remaining = int(data["quota_remaining"])
                if data.get("backoff"):
                    self.client.defer(float(data["backoff"]))
                for item in data.get("items") or []:
                    signal = self.map_question(item, site)
                    if signal is not None:
                        yield signal
                if not data.get("has_more"):
                    break

    @staticmethod
    def map_question(item: dict, site: str) -> RawSignal | None:
        qid = item.get("question_id")
        if qid is None or not item.get("link"):
            return None
        owner = item.get("owner") or {}
        handle = str(owner["user_id"]) if owner.get("user_id") is not None else None
        return RawSignal(
            source_platform="stackexchange",
            external_id=f"{site}:{qid}",
            url=item["link"],
            title=html_to_text(item.get("title")),
            body=html_to_text(item.get("body")),
            author_handle_hash=hash_author(f"stackexchange:{site}", handle),
            score=item.get("score"),
            comment_count=item.get("answer_count"),
            tags=list(item.get("tags") or []),
            source_created_at=from_unix(item.get("creation_date")),
        )
