from __future__ import annotations

import gzip
import json
from pathlib import Path

from scrapers.http_client import HttpRequest, HttpResponse

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(rel: str) -> bytes:
    return (FIXTURES / rel).read_bytes()


class FakeTransport:
    """Replays queued responses; records every request. No network, ever."""

    def __init__(self, responses: list[HttpResponse | Exception]) -> None:
        self.responses = list(responses)
        self.requests: list[HttpRequest] = []

    def __call__(self, request: HttpRequest, timeout: float) -> HttpResponse:
        self.requests.append(request)
        if not self.responses:
            raise AssertionError(f"unexpected request: {request.url}")
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def ok(body: bytes | dict, headers: dict | None = None, *, gz: bool = False) -> HttpResponse:
    data = json.dumps(body).encode() if isinstance(body, dict) else body
    hdrs = dict(headers or {})
    if gz:
        data = gzip.compress(data)
        hdrs["Content-Encoding"] = "gzip"
    return HttpResponse(200, hdrs, data)


def status(code: int, headers: dict | None = None) -> HttpResponse:
    return HttpResponse(code, headers or {}, b"{}")


class FakeClock:
    def __init__(self, start: float = 1_763_300_000.0) -> None:
        self.now = start
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds
