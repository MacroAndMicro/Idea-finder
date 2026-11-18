import urllib.error

import pytest

from scrapers.http_client import HttpError, RateLimitExceeded
from scrapers.tests.helpers import ok, status


def test_sends_honest_user_agent_and_gzip(make_client, monkeypatch):
    monkeypatch.setenv("SCRAPER_USER_AGENT", "idea-finder/test")
    client, transport = make_client([ok({"a": 1}, gz=True)])
    assert client.get("https://api.example.com/x", {"q": "a b", "skip": None}).json() == {"a": 1}
    req = transport.requests[0]
    assert req.headers["User-Agent"] == "idea-finder/test"
    assert req.url == "https://api.example.com/x?q=a+b"


def test_retries_429_honoring_retry_after(make_client, clock):
    client, transport = make_client([status(429, {"Retry-After": "7"}), ok({"ok": True})])
    assert client.get("https://api.example.com/x").json() == {"ok": True}
    assert clock.sleeps == [7.0]
    assert len(transport.requests) == 2


def test_exponential_backoff_on_5xx_and_network_errors(make_client, clock):
    client, _ = make_client(
        [status(503), urllib.error.URLError("boom"), status(502), ok({})], backoff_base=1.0
    )
    client.get("https://api.example.com/x")
    assert clock.sleeps == [1.0, 2.0, 4.0]


def test_gives_up_after_max_retries(make_client):
    client, _ = make_client([status(500)] * 3, max_retries=2)
    with pytest.raises(RateLimitExceeded):
        client.get("https://api.example.com/x")


def test_non_retryable_error_raises_without_query_string(make_client):
    client, _ = make_client([status(404)])
    with pytest.raises(HttpError) as exc:
        client.get("https://api.example.com/x", {"key": "SECRET"})
    assert exc.value.status == 404
    assert "SECRET" not in str(exc.value)


def test_403_with_ratelimit_reset_waits_until_reset(make_client, clock):
    reset = int(clock.now) + 30
    client, _ = make_client(
        [status(403, {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(reset)}), ok({})]
    )
    client.get("https://api.example.com/x")
    assert clock.sleeps == [31.0]


def test_wait_longer_than_max_wait_stops(make_client):
    client, _ = make_client([status(429, {"Retry-After": "3600"})], max_wait=60)
    with pytest.raises(RateLimitExceeded):
        client.get("https://api.example.com/x")


def test_exhausted_primary_limit_defers_next_request(make_client, clock):
    reset = int(clock.now) + 10
    client, _ = make_client(
        [ok({}, {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(reset)}), ok({})]
    )
    client.get("https://api.example.com/x")
    assert clock.sleeps == []
    client.get("https://api.example.com/x")
    assert clock.sleeps == [11.0]


def test_min_interval_spaces_requests(make_client, clock):
    client, _ = make_client([ok({}), ok({})], min_interval=2.0)
    client.get("https://api.example.com/x")
    client.get("https://api.example.com/x")
    assert clock.sleeps == [2.0]


def test_retry_hint_too_long_raises_quota_exhausted_without_retry(make_client, clock):
    from scrapers.http_client import QuotaExhausted

    client, transport = make_client([status(429), ok({})], max_wait=60,
                                    retry_hint=lambda resp: 17399.0)
    with pytest.raises(QuotaExhausted):
        client.get("https://api.example.com/x")
    assert len(transport.requests) == 1 and clock.sleeps == []


def test_short_retry_hint_is_honoured(make_client, clock):
    client, _ = make_client([status(429), ok({})], retry_hint=lambda resp: 5.0)
    client.get("https://api.example.com/x")
    assert clock.sleeps == [5.0]
