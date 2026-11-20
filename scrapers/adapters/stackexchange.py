"""Stack Exchange via the official API v2.3 (requires STACKEXCHANGE_KEY).

Honors the response ``backoff`` field (no request to the same method before it
elapses) and stops when ``quota_remaining`` drops below a safety floor.
Responses are always gzip-compressed; the shared client decodes them.

Rolling look-back (IF-94): ``fromdate`` is the earlier of the run's ``since`` and
now - STACKEXCHANGE_LOOKBACK_DAYS (default 14), sorted by ``activity`` so questions that
earned answers/votes after they were posted resurface; re-seen questions are skipped by
the store's (source_platform, external_id) de-dup. Negative-score questions are dropped.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator, Sequence
from datetime import UTC, datetime

from scrapers import config
from scrapers.adapters.base import SourceAdapter, interleave, rolling_window_start
from scrapers.http_client import HttpClient
from scrapers.models import RawSignal, from_unix, hash_author, html_to_text

log = logging.getLogger(__name__)

SEARCH_URL = "https://api.stackexchange.com/2.3/search/advanced"
DEFAULT_SITES = ("stackoverflow", "serverfault", "superuser")
PAGE_SIZE = 100
QUOTA_FLOOR = 50  # keep headroom for other jobs sharing the daily key quota
MIN_INTERVAL_SECONDS = 0.5  # API asks for < 30 req/s; we stay well under
#: Rolling look-back (IF-94): a ~4h ``since`` window held 0-1 questions per query/site, and
#: questions were captured at birth (score 0, no answers). Never search less than this.
DEFAULT_LOOKBACK_DAYS = 14
LOOKBACK_ENV = "STACKEXCHANGE_LOOKBACK_DAYS"
#: ``activity`` resurfaces questions that gained answers/votes/edits inside the window.
SORT = "activity"
#: Questions scored below this by the community are noise (unclear, off-topic, duplicate).
MIN_SCORE = 0


def lookback_from_env() -> int:
    """``STACKEXCHANGE_LOOKBACK_DAYS`` (int >= 0), else DEFAULT_LOOKBACK_DAYS with a warning."""
    raw = config.get_env(LOOKBACK_ENV)
    if raw is None:
        return DEFAULT_LOOKBACK_DAYS
    try:
        value = int(raw)
    except ValueError:
        value = -1
    if value < 0:
        log.warning("%s must be an integer >= 0; using %d", LOOKBACK_ENV, DEFAULT_LOOKBACK_DAYS)
        return DEFAULT_LOOKBACK_DAYS
    return value


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
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        super().__init__(client or HttpClient(min_interval=MIN_INTERVAL_SECONDS),
                         max_pages=max_pages)
        self._key = key
        self.sites = tuple(sites)
        self.quota_floor = quota_floor
        self.quota_remaining: int | None = None
        self.lookback_days = lookback_days
        self._now = now

    @classmethod
    def from_env(cls, **kwargs) -> StackExchangeAdapter:
        sites = config.get_env("STACKEXCHANGE_SITES")
        if sites:
            kwargs.setdefault("sites", [s.strip() for s in sites.split(",") if s.strip()])
        kwargs.setdefault("lookback_days", lookback_from_env())
        return cls(config.get_env("STACKEXCHANGE_KEY"), **kwargs)

    def fetch_all(self, queries: Sequence[str], since: datetime) -> Iterator[RawSignal]:
        """Round-robin over every (query, site) pair (IF-94): with a 14-day window the first
        pair alone can fill ``--limit``. Pages stay lazy, so the page cap is unchanged."""
        if not self._key:
            log.warning("STACKEXCHANGE_KEY is not set; skipping Stack Exchange ingestion")
            return iter(())
        return interleave(self._fetch_site(q, site, since) for q in queries for site in self.sites)

    def fetch(self, query: str, since: datetime) -> Iterator[RawSignal]:
        if not self._key:
            log.warning("STACKEXCHANGE_KEY is not set; skipping Stack Exchange ingestion")
            return
        for site in self.sites:
            yield from self._fetch_site(query, site, since)

    def _fetch_site(self, query: str, site: str, since: datetime) -> Iterator[RawSignal]:
        fromdate = int(rolling_window_start(since, self._now(), self.lookback_days).timestamp())
        for page in range(1, self.max_pages + 1):
            if self.quota_remaining is not None and self.quota_remaining < self.quota_floor:
                log.warning("Stack Exchange quota low (%s); stopping", self.quota_remaining)
                return
            data = self.client.get(
                SEARCH_URL,
                {
                    "q": query,
                    "site": site,
                    "fromdate": fromdate,
                    "sort": SORT,
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
                if (item.get("score") or 0) < MIN_SCORE:
                    continue
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
