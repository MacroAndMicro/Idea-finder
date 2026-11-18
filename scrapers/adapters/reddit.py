"""Reddit via the official OAuth API (app-only, client credentials).

Needs REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET and REDDIT_USER_AGENT (Reddit requires a
unique, descriptive User-Agent; we send exactly the configured one, never a browser's).
The token comes from the official ``/api/v1/access_token`` endpoint; every data call
goes to ``oauth.reddit.com``. No www/old.reddit HTML is ever fetched.

Rate limits: Reddit reports ``X-Ratelimit-Remaining`` / ``X-Ratelimit-Reset`` (seconds
until the window resets); the shared HttpClient waits for the reset when the budget is
spent and backs off on 429/5xx. Requests are also spaced by ``MIN_INTERVAL_SECONDS``.

Only submissions are ingested (subreddit search, newest first, stops at ``since``);
comments would cost one extra request per post and are left for later.
NSFW, promoted and stickied posts are skipped.
"""

from __future__ import annotations

import base64
import logging
import re
import time
from collections.abc import Callable, Iterator, Sequence
from datetime import datetime

from scrapers import config
from scrapers.adapters.base import SourceAdapter
from scrapers.http_client import HttpClient, HttpError
from scrapers.models import RawSignal, from_unix, hash_author

log = logging.getLogger(__name__)

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"  # noqa: S105 - URL, not a secret
API_BASE = "https://oauth.reddit.com"
WEB_BASE = "https://www.reddit.com"
#: B2B / developer communities where workflow pain is discussed; override with
#: REDDIT_SUBREDDITS (comma-separated).
DEFAULT_SUBREDDITS = (
    "sysadmin", "devops", "SaaS", "dataengineering", "ExperiencedDevs", "msp",
    "salesforce", "analytics",
)
PAGE_SIZE = 100
MIN_INTERVAL_SECONDS = 1.0  # OAuth clients get ~100 requests/min; we stay at <= 60
TOKEN_REFRESH_MARGIN = 60   # seconds before expiry to fetch a new token
_SUBREDDIT_RE = re.compile(r"^[A-Za-z0-9_]{2,21}$")
REQUIRED_VARS = ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USER_AGENT")


class RedditAdapter(SourceAdapter):
    platform = "reddit"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        user_agent: str,
        client: HttpClient | None = None,
        *,
        subreddits: Sequence[str] = DEFAULT_SUBREDDITS,
        max_pages: int = 2,
        clock: Callable[[], float] = time.time,
    ) -> None:
        super().__init__(
            client or HttpClient(min_interval=MIN_INTERVAL_SECONDS,
                                 default_headers={"User-Agent": user_agent}),
            max_pages=max_pages,
        )
        bad = [s for s in subreddits if not _SUBREDDIT_RE.match(s)]
        if bad:
            raise ValueError(f"invalid subreddit name(s): {bad}")
        self._auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        self._user_agent = user_agent
        self.subreddits = tuple(subreddits)
        self._clock = clock
        self._token: str | None = None
        self._token_expires = 0.0

    @classmethod
    def from_env(cls, **kwargs) -> RedditAdapter:
        """Raises MissingSecretError naming the first missing REDDIT_* variable."""
        values = [config.require_env(name) for name in REQUIRED_VARS]
        subs = config.get_env("REDDIT_SUBREDDITS")
        if subs:
            kwargs.setdefault("subreddits", [s.strip() for s in subs.split(",") if s.strip()])
        return cls(*values, **kwargs)

    @staticmethod
    def missing_env() -> list[str]:
        return [name for name in REQUIRED_VARS if config.get_env(name) is None]

    def _bearer(self) -> str:
        if self._token and self._clock() < self._token_expires - TOKEN_REFRESH_MARGIN:
            return self._token
        data = self.client.post_form(
            TOKEN_URL, {"grant_type": "client_credentials"},
            {"Authorization": f"Basic {self._auth}", "User-Agent": self._user_agent},
        ).json()
        token = data.get("access_token") if isinstance(data, dict) else None
        if not token:
            # never include the response: it could echo credentials
            raise HttpError(401, TOKEN_URL, "no access_token in token response")
        self._token = str(token)
        self._token_expires = self._clock() + float(data.get("expires_in") or 3600)
        return self._token

    def time_filter(self, since: datetime) -> str:
        """Smallest Reddit search window (``t``) that still covers ``since``."""
        age_days = (self._clock() - since.timestamp()) / 86_400
        for limit, name in ((1, "day"), (7, "week"), (30, "month"), (365, "year")):
            if age_days <= limit:
                return name
        return "all"

    def fetch(self, query: str, since: datetime) -> Iterator[RawSignal]:
        cutoff = since.timestamp()
        window = self.time_filter(since)
        for sub in self.subreddits:
            after: str | None = None
            for _page in range(self.max_pages):
                resp = self.client.get(
                    f"{API_BASE}/r/{sub}/search",
                    {"q": query, "restrict_sr": 1, "sort": "new", "t": window,
                     "type": "link", "limit": PAGE_SIZE, "after": after, "raw_json": 1},
                    {"Authorization": f"bearer {self._bearer()}",
                     "User-Agent": self._user_agent},
                ).json()
                listing = (resp or {}).get("data") or {}
                reached_cutoff = False
                for child in listing.get("children") or []:
                    if child.get("kind") != "t3":
                        continue
                    post = child.get("data") or {}
                    created = post.get("created_utc")
                    if created is not None and float(created) < cutoff:
                        reached_cutoff = True  # sorted newest first: the rest are older
                        break
                    signal = self.map_post(post)
                    if signal is not None:
                        yield signal
                after = listing.get("after")
                if reached_cutoff or not after:
                    break

    @staticmethod
    def map_post(post: dict) -> RawSignal | None:
        name, permalink = post.get("name"), post.get("permalink") or ""
        if not name or not permalink.startswith("/r/"):
            return None
        if post.get("over_18") or post.get("promoted") or post.get("stickied"):
            return None
        author = post.get("author")
        handle = None if author in (None, "[deleted]", "[removed]") else str(author)
        body = (post.get("selftext") or "").strip()
        tags = [t for t in (post.get("subreddit"), post.get("link_flair_text")) if t]
        return RawSignal(
            source_platform="reddit",
            external_id=str(name),
            url=f"{WEB_BASE}{permalink}",
            title=post.get("title"),
            body=None if body in ("", "[deleted]", "[removed]") else body,
            author_handle_hash=hash_author("reddit", handle),
            score=post.get("score"),
            comment_count=post.get("num_comments"),
            tags=tags,
            source_created_at=from_unix(post.get("created_utc")),
        )

