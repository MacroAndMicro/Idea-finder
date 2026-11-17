"""GitHub issues via the official REST search API (requires GITHUB_TOKEN).

Search API: 30 requests/minute authenticated, max 1000 results per query.
Requests are sequential with a minimum interval; X-RateLimit-* and secondary
limits (403/429 + Retry-After) are honored by the shared HttpClient.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import datetime

from scrapers import config
from scrapers.adapters.base import SourceAdapter
from scrapers.http_client import HttpClient
from scrapers.models import RawSignal, hash_author, html_to_text

log = logging.getLogger(__name__)

SEARCH_URL = "https://api.github.com/search/issues"
PER_PAGE = 100
MAX_SEARCH_RESULTS = 1000
MIN_INTERVAL_SECONDS = 2.5  # 30 req/min search limit → never burst
BODY_MAX_CHARS = 8000


class GitHubIssuesAdapter(SourceAdapter):
    platform = "github"

    def __init__(
        self,
        token: str | None,
        client: HttpClient | None = None,
        *,
        max_pages: int = 3,
        label: str | None = None,
        min_reactions: int = 3,
    ) -> None:
        super().__init__(client or HttpClient(min_interval=MIN_INTERVAL_SECONDS),
                         max_pages=max_pages)
        self._token = token
        self.label = label
        self.min_reactions = min_reactions

    @classmethod
    def from_env(cls, **kwargs) -> GitHubIssuesAdapter:
        return cls(config.get_env("GITHUB_TOKEN"), **kwargs)

    def build_query(self, query: str, since: datetime) -> str:
        parts = [query, "is:issue", f"created:>{since:%Y-%m-%d}"]
        if self.min_reactions:
            parts.append(f"reactions:>={self.min_reactions}")
        if self.label:
            parts.append(f'label:"{self.label}"')
        return " ".join(p for p in parts if p)

    def fetch(self, query: str, since: datetime) -> Iterator[RawSignal]:
        if not self._token:
            log.warning("GITHUB_TOKEN is not set; skipping GitHub ingestion")
            return
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        q = self.build_query(query, since)
        seen = 0
        for page in range(1, self.max_pages + 1):
            data = self.client.get(
                SEARCH_URL,
                {"q": q, "sort": "created", "order": "desc", "per_page": PER_PAGE, "page": page},
                headers=headers,
            ).json()
            items = data.get("items") or []
            for item in items:
                signal = self.map_issue(item)
                if signal is not None:
                    yield signal
            seen += len(items)
            total = min(int(data.get("total_count") or 0), MAX_SEARCH_RESULTS)
            if len(items) < PER_PAGE or seen >= total:
                return

    @staticmethod
    def map_issue(item: dict) -> RawSignal | None:
        if "pull_request" in item:
            return None
        repo = (item.get("repository_url") or "").removeprefix("https://api.github.com/repos/")
        number = item.get("number")
        if not repo or number is None or not item.get("html_url"):
            return None
        body = html_to_text(item.get("body"))  # markdown, but may embed HTML
        if body and len(body) > BODY_MAX_CHARS:
            body = body[:BODY_MAX_CHARS]
        created = item.get("created_at")
        return RawSignal(
            source_platform="github",
            external_id=f"{repo}#{number}",
            url=item["html_url"],
            title=item.get("title"),
            body=body,
            author_handle_hash=hash_author("github", (item.get("user") or {}).get("login")),
            score=(item.get("reactions") or {}).get("total_count"),
            comment_count=item.get("comments"),
            tags=[lbl["name"] for lbl in item.get("labels") or [] if lbl.get("name")],
            source_created_at=datetime.fromisoformat(created) if created else None,
        )
