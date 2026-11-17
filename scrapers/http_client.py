"""Shared, polite HTTP client for official source APIs.

- per-request timeout
- retries with exponential backoff on network errors, 429 and 5xx
- honors Retry-After and X-RateLimit-Remaining / X-RateLimit-Reset
- optional minimum interval between requests (no parallel bursts)
- transparent gzip decoding
- honest User-Agent (see config.user_agent); never spoofed

The network call is an injectable ``transport`` so tests use recorded fixtures only.
"""

from __future__ import annotations

import gzip
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from scrapers import config

log = logging.getLogger(__name__)

RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})


@dataclass(frozen=True)
class HttpRequest:
    method: str
    url: str
    headers: Mapping[str, str] = field(default_factory=dict)
    body: bytes | None = None


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes

    def header(self, name: str) -> str | None:
        lname = name.lower()
        for key, value in self.headers.items():
            if key.lower() == lname:
                return value
        return None

    def text(self) -> str:
        data = self.body
        if self.header("Content-Encoding") == "gzip" or data[:2] == b"\x1f\x8b":
            data = gzip.decompress(data)
        return data.decode("utf-8")

    def json(self) -> Any:
        return json.loads(self.text())


class HttpError(RuntimeError):
    def __init__(self, status: int, url: str, detail: str = "") -> None:
        # URL is logged without the query string so keys passed as params never leak.
        super().__init__(f"HTTP {status} for {_redact(url)} {detail}".strip())
        self.status = status


class RateLimitExceeded(HttpError):
    """The API asked us to wait longer than ``max_wait``; caller should stop."""


Transport = Callable[[HttpRequest, float], HttpResponse]


def urllib_transport(request: HttpRequest, timeout: float) -> HttpResponse:
    req = urllib.request.Request(  # noqa: S310 - https URLs built by adapters
        request.url, data=request.body, headers=dict(request.headers), method=request.method
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return HttpResponse(resp.status, dict(resp.headers.items()), resp.read())
    except urllib.error.HTTPError as exc:
        return HttpResponse(exc.code, dict(exc.headers.items()), exc.read() or b"")


def _redact(url: str) -> str:
    return urllib.parse.urlsplit(url)._replace(query="", fragment="").geturl()


class HttpClient:
    def __init__(
        self,
        *,
        transport: Transport = urllib_transport,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.time,
        timeout: float = 20.0,
        max_retries: int = 4,
        backoff_base: float = 1.0,
        max_wait: float = 900.0,
        min_interval: float = 0.0,
        default_headers: Mapping[str, str] | None = None,
    ) -> None:
        self._transport = transport
        self._sleep = sleep
        self._clock = clock
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.max_wait = max_wait
        self.min_interval = min_interval
        self._headers = {"User-Agent": config.user_agent(), "Accept-Encoding": "gzip"}
        self._headers.update(default_headers or {})
        self._last_request: float | None = None
        self._not_before: float = 0.0

    def defer(self, seconds: float) -> None:
        """Ask the client not to send another request for ``seconds`` (e.g. SE `backoff`)."""
        if seconds > self.max_wait:
            raise RateLimitExceeded(429, "", f"backoff {seconds:.0f}s exceeds max_wait")
        self._not_before = max(self._not_before, self._clock() + seconds)

    def _wait_turn(self) -> None:
        now = self._clock()
        wait = self._not_before - now
        if self._last_request is not None and self.min_interval:
            wait = max(wait, self._last_request + self.min_interval - now)
        if wait > 0:
            self._sleep(wait)
        self._last_request = self._clock()

    def _server_wait(self, resp: HttpResponse) -> float | None:
        retry_after = resp.header("Retry-After")
        if retry_after:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                return None
        if resp.header("X-RateLimit-Remaining") == "0" and resp.header("X-RateLimit-Reset"):
            try:
                return max(0.0, float(resp.header("X-RateLimit-Reset") or 0) - self._clock()) + 1
            except ValueError:
                return None
        return None

    def get(
        self,
        url: str,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> HttpResponse:
        if params:
            clean = {k: v for k, v in params.items() if v is not None}
            url = f"{url}?{urllib.parse.urlencode(clean)}"
        request = HttpRequest("GET", url, {**self._headers, **(headers or {})})
        return self.send(request)

    def post_json(
        self, url: str, payload: Any, headers: Mapping[str, str] | None = None
    ) -> HttpResponse:
        merged = {**self._headers, "Content-Type": "application/json", **(headers or {})}
        return self.send(HttpRequest("POST", url, merged, json.dumps(payload).encode()))

    def send(self, request: HttpRequest) -> HttpResponse:
        attempt = 0
        while True:
            self._wait_turn()
            try:
                resp = self._transport(request, self.timeout)
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                if attempt >= self.max_retries:
                    raise HttpError(0, request.url, f"network error: {exc}") from exc
                delay = self.backoff_base * 2**attempt
                log.warning("network error on %s; retry in %.1fs", _redact(request.url), delay)
                self._sleep(delay)
                attempt += 1
                continue

            server_wait = self._server_wait(resp)
            throttled = resp.status in RETRY_STATUSES or (
                resp.status == 403 and server_wait is not None
            )
            if 200 <= resp.status < 300:
                # Primary rate limit exhausted: wait for the reset before the next call.
                if server_wait is not None and resp.header("X-RateLimit-Remaining") == "0":
                    self.defer(server_wait)
                return resp
            if not throttled:
                raise HttpError(resp.status, request.url)
            if attempt >= self.max_retries:
                raise RateLimitExceeded(resp.status, request.url, "retries exhausted")
            delay = server_wait if server_wait is not None else self.backoff_base * 2**attempt
            if delay > self.max_wait:
                raise RateLimitExceeded(resp.status, request.url, f"wait {delay:.0f}s too long")
            log.warning("HTTP %s on %s; retry in %.1fs", resp.status, _redact(request.url), delay)
            self._sleep(delay)
            attempt += 1
