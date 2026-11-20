"""GitHub issues via the official REST search API (requires GITHUB_TOKEN).

Search API: 30 requests/minute authenticated, max 1000 results per query.
Requests are sequential with a minimum interval; X-RateLimit-* and secondary
limits (403/429 + Retry-After) are honored by the shared HttpClient.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Iterator, Sequence
from datetime import UTC, datetime, timedelta

from scrapers import config
from scrapers.adapters.base import SourceAdapter
from scrapers.http_client import HttpClient, HttpError
from scrapers.models import RawSignal, hash_author, html_to_text

log = logging.getLogger(__name__)

SEARCH_URL = "https://api.github.com/search/issues"
PER_PAGE = 100
MAX_SEARCH_RESULTS = 1000
MIN_INTERVAL_SECONDS = 2.5  # 30 req/min search limit → never burst
BODY_MAX_CHARS = 8000
#: Rolling look-back for issue search (IF-93). ``reactions:>=N`` needs time to accrue, so
#: the created window is never shorter than this many days, however recent the last run
#: was; already-stored issues are skipped by the store's (platform, external_id) de-dup.
DEFAULT_ISSUE_LOOKBACK_DAYS = 14
ISSUE_LOOKBACK_ENV = "GITHUB_ISSUE_LOOKBACK_DAYS"


def created_filter(since: datetime) -> str:
    """GitHub search qualifier including everything created at/after ``since``.

    A date-only ``created:>YYYY-MM-DD`` means "from the next day", which silently
    dropped the rest of the since day (IF-83). Use the full UTC instant instead;
    naive datetimes are treated as UTC.
    """
    if since.tzinfo is None:
        since = since.replace(tzinfo=UTC)
    return f"created:>={since.astimezone(UTC):%Y-%m-%dT%H:%M:%SZ}"


def issue_window_start(since: datetime, now: datetime, lookback_days: int) -> datetime:
    """Start of the issue ``created`` window: the earlier of ``since`` and now - lookback.

    The run window (``since``) is ~4h after IF-75; issues that young rarely have the
    ``reactions:>=N`` they need, and once they do they are outside the next run's window
    (IF-93). ``lookback_days <= 0`` disables the rolling window (plain ``since``).
    """
    if since.tzinfo is None:
        since = since.replace(tzinfo=UTC)
    if lookback_days <= 0:
        return since
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    return min(since, now - timedelta(days=lookback_days))


def issue_lookback_from_env() -> int:
    """``GITHUB_ISSUE_LOOKBACK_DAYS`` (int >= 0), else DEFAULT_ISSUE_LOOKBACK_DAYS."""
    raw = config.get_env(ISSUE_LOOKBACK_ENV)
    if raw is None or not raw.strip():
        return DEFAULT_ISSUE_LOOKBACK_DAYS
    try:
        value = int(raw.strip())
    except ValueError:
        value = -1
    if value < 0:
        log.warning("%s must be an integer >= 0; using %d", ISSUE_LOOKBACK_ENV,
                    DEFAULT_ISSUE_LOOKBACK_DAYS)
        return DEFAULT_ISSUE_LOOKBACK_DAYS
    return value


def interleave(streams: Iterable[Iterator[RawSignal]]) -> Iterator[RawSignal]:
    """Round-robin over lazy streams until all are exhausted."""
    active = list(streams)
    while active:
        for stream in list(active):
            try:
                yield next(stream)
            except StopIteration:
                active.remove(stream)


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
        lookback_days: int = DEFAULT_ISSUE_LOOKBACK_DAYS,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        super().__init__(client or HttpClient(min_interval=MIN_INTERVAL_SECONDS),
                         max_pages=max_pages)
        self._token = token
        self.label = label
        self.min_reactions = min_reactions
        self.lookback_days = lookback_days
        self._now = now

    @classmethod
    def from_env(cls, **kwargs) -> GitHubIssuesAdapter:
        return cls(config.get_env("GITHUB_TOKEN"), **kwargs)

    def build_query(self, query: str, since: datetime) -> str:
        start = issue_window_start(since, self._now(), self.lookback_days)
        parts = [query, "is:issue", created_filter(start)]
        if self.min_reactions:
            parts.append(f"reactions:>={self.min_reactions}")
        if self.label:
            parts.append(f'label:"{self.label}"')
        return " ".join(p for p in parts if p)

    def fetch_all(self, queries: Sequence[str], since: datetime) -> Iterator[RawSignal]:
        """Round-robin over queries (IF-93): with a multi-day window the first query alone
        can fill ``--limit``; pages stay lazy, so the per-query page cap is unchanged."""
        return interleave(self.fetch(q, since) for q in queries)

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


GRAPHQL_URL = "https://api.github.com/graphql"
#: GraphQL search page size (max 100); small pages keep the point cost per request low.
DISCUSSIONS_PER_PAGE = 50
DISCUSSION_PREFIX = "discussion:"
DISCUSSION_SEARCH = """
query($q: String!, $first: Int!, $after: String) {
  search(query: $q, type: DISCUSSION, first: $first, after: $after) {
    pageInfo { hasNextPage endCursor }
    nodes {
      ... on Discussion {
        number title body url createdAt upvoteCount
        comments { totalCount }
        author { login }
        repository { nameWithOwner }
        category { name }
      }
    }
  }
}
""".strip()


class GitHubDiscussionsAdapter(SourceAdapter):
    """GitHub Discussions via the official GraphQL API (``search(type: DISCUSSION)``).

    Plain HTTPS POST through the shared HttpClient (same backoff / X-RateLimit handling
    as issues); at most ``max_pages`` pages per query. GraphQL errors stop the query
    with a warning instead of failing the whole GitHub run.
    """

    platform = "github"

    def __init__(self, token: str | None, client: HttpClient | None = None, *,
                 max_pages: int = 2) -> None:
        super().__init__(client or HttpClient(min_interval=MIN_INTERVAL_SECONDS),
                         max_pages=max_pages)
        self._token = token

    @staticmethod
    def build_query(query: str, since: datetime) -> str:
        return " ".join(p for p in (query, created_filter(since)) if p)

    def fetch(self, query: str, since: datetime) -> Iterator[RawSignal]:
        if not self._token:
            log.warning("GITHUB_TOKEN is not set; skipping GitHub Discussions ingestion")
            return
        headers = {"Authorization": f"Bearer {self._token}"}
        variables: dict = {"q": self.build_query(query, since),
                           "first": DISCUSSIONS_PER_PAGE, "after": None}
        for _ in range(self.max_pages):
            data = self.client.post_json(
                GRAPHQL_URL, {"query": DISCUSSION_SEARCH, "variables": variables},
                headers=headers,
            ).json() or {}
            if data.get("errors"):
                kinds = sorted({str(e.get("type") or "error") for e in data["errors"]
                                if isinstance(e, dict)})
                log.warning("GitHub GraphQL discussion search returned errors %s; "
                            "stopping this query", kinds)
                return
            search = ((data.get("data") or {}).get("search")) or {}
            for node in search.get("nodes") or []:
                signal = self.map_discussion(node)
                if signal is not None:
                    yield signal
            page = search.get("pageInfo") or {}
            if not page.get("hasNextPage") or not page.get("endCursor"):
                return
            variables["after"] = page["endCursor"]

    @staticmethod
    def map_discussion(node: dict) -> RawSignal | None:
        if not isinstance(node, dict):
            return None
        repo = (node.get("repository") or {}).get("nameWithOwner")
        number = node.get("number")
        url = node.get("url")
        if not repo or number is None or not url:
            return None
        body = html_to_text(node.get("body"))
        if body and len(body) > BODY_MAX_CHARS:
            body = body[:BODY_MAX_CHARS]
        created = node.get("createdAt")
        category = (node.get("category") or {}).get("name")
        return RawSignal(
            source_platform="github",
            external_id=f"{DISCUSSION_PREFIX}{repo}#{number}",
            url=url,
            title=node.get("title"),
            body=body,
            author_handle_hash=hash_author("github", (node.get("author") or {}).get("login")),
            score=node.get("upvoteCount"),
            comment_count=(node.get("comments") or {}).get("totalCount"),
            tags=["discussion", *([category] if category else [])],
            source_created_at=(datetime.fromisoformat(created.replace("Z", "+00:00"))
                               if created else None),
        )


class GitHubAdapter(SourceAdapter):
    """The ``github`` source: issues (REST search) + discussions (GraphQL), one client.

    ``fetch`` = issues only (backwards compatible). ``fetch_all`` interleaves the issue
    stream (``queries``) with the discussion stream (``discussion_queries``) so a shared
    ``--limit`` reaches both.
    """

    platform = "github"

    def __init__(self, token: str | None, client: HttpClient | None = None, *,
                 discussion_queries: Sequence[str] = (), max_pages: int = 3,
                 issue_lookback_days: int = DEFAULT_ISSUE_LOOKBACK_DAYS) -> None:
        super().__init__(client or HttpClient(min_interval=MIN_INTERVAL_SECONDS),
                         max_pages=max_pages)
        self.issues = GitHubIssuesAdapter(token, self.client, max_pages=max_pages,
                                          lookback_days=issue_lookback_days)
        self.discussions = GitHubDiscussionsAdapter(token, self.client)
        self.discussion_queries = tuple(discussion_queries)

    @classmethod
    def from_env(cls, **kwargs) -> GitHubAdapter:
        override = config.get_env("GITHUB_DISCUSSION_QUERIES")
        if override:
            kwargs.setdefault("discussion_queries",
                              [q.strip() for q in override.split(",") if q.strip()])
        kwargs.setdefault("issue_lookback_days", issue_lookback_from_env())
        return cls(config.get_env("GITHUB_TOKEN"), **kwargs)

    def fetch(self, query: str, since: datetime) -> Iterator[RawSignal]:
        return self.issues.fetch(query, since)

    def _safe_discussions(self, since: datetime) -> Iterator[RawSignal]:
        """Discussions are additive: an HTTP failure (e.g. GraphQL blocked by an egress
        proxy, 403) ends the discussion stream with a warning and never fails issues."""
        try:
            yield from self.discussions.fetch_all(self.discussion_queries, since)
        except HttpError as exc:
            log.warning("GitHub Discussions unavailable (HTTP %s); continuing with issues only",
                        exc.status)

    def fetch_all(self, queries: Sequence[str], since: datetime) -> Iterator[RawSignal]:
        return interleave([self.issues.fetch_all(queries, since),
                           self._safe_discussions(since)])
