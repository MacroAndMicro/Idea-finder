"""Hacker News via the official Algolia HN Search API (no key required).

Two searches per query: Ask HN stories and comments, both restricted to
``created_at_i > since`` and paginated until ``nbPages`` or ``max_pages``.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime

from scrapers.adapters.base import SourceAdapter
from scrapers.http_client import HttpClient
from scrapers.models import RawSignal, from_unix, hash_author, html_to_text

ALGOLIA_SEARCH_URL = "https://hn.algolia.com/api/v1/search_by_date"
ITEM_URL = "https://news.ycombinator.com/item?id={id}"
HITS_PER_PAGE = 100
# Algolia allows ~10k requests/hour per IP; one request per second keeps us far below.
MIN_INTERVAL_SECONDS = 1.0


class HackerNewsAdapter(SourceAdapter):
    platform = "hackernews"

    def __init__(
        self, client: HttpClient | None = None, *, max_pages: int = 5,
        include_comments: bool = True,
    ) -> None:
        super().__init__(client or HttpClient(min_interval=MIN_INTERVAL_SECONDS),
                         max_pages=max_pages)
        self.include_comments = include_comments

    def fetch(self, query: str, since: datetime) -> Iterator[RawSignal]:
        tag_sets = ["ask_hn"] + (["comment"] if self.include_comments else [])
        for tags in tag_sets:
            yield from self._search(query, since, tags)

    def _search(self, query: str, since: datetime, tags: str) -> Iterator[RawSignal]:
        page = 0
        while page < self.max_pages:
            data = self.client.get(
                ALGOLIA_SEARCH_URL,
                {
                    "query": query,
                    "tags": tags,
                    "numericFilters": f"created_at_i>{int(since.timestamp())}",
                    "hitsPerPage": HITS_PER_PAGE,
                    "page": page,
                },
            ).json()
            hits = data.get("hits") or []
            for hit in hits:
                signal = self.map_hit(hit)
                if signal is not None:
                    yield signal
            page = int(data.get("page", page)) + 1
            if not hits or page >= int(data.get("nbPages") or 0):
                return

    @staticmethod
    def map_hit(hit: dict) -> RawSignal | None:
        object_id = hit.get("objectID")
        if not object_id:
            return None
        is_comment = "comment" in (hit.get("_tags") or [])
        body = html_to_text(hit.get("comment_text") if is_comment else hit.get("story_text"))
        title = hit.get("story_title") if is_comment else hit.get("title")
        if not body and not title:
            return None
        return RawSignal(
            source_platform="hackernews",
            external_id=str(object_id),
            url=ITEM_URL.format(id=object_id),
            title=title,
            body=body,
            author_handle_hash=hash_author("hackernews", hit.get("author")),
            score=hit.get("points"),
            comment_count=None if is_comment else hit.get("num_comments"),
            tags=["comment"] if is_comment else ["ask_hn"],
            source_created_at=from_unix(hit.get("created_at_i")),
        )
