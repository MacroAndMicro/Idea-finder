"""IF-81: auth header values must never reach exception messages or logs."""

import logging
import urllib.error

import pytest

from scrapers.http_client import HttpError, QuotaExhausted, RateLimitExceeded
from scrapers.tests.helpers import status

FAKE_TOKEN = "ghp_FAKE_TOKEN_must_not_leak_1234567890"
FAKE_KEY = "fake-api-key-must-not-leak-0987"
URL = "https://api.example.com/repos/o/r/issues"

AUTH_HEADERS = {
    "Authorization": f"Bearer {FAKE_TOKEN}",
    "X-API-Key": FAKE_KEY,
}


def _assert_clean(text: str) -> None:
    assert FAKE_TOKEN not in text
    assert FAKE_KEY not in text
    assert "Bearer" not in text


@pytest.fixture
def per_request_and_default(make_client):
    """Exercise both ways headers reach a request: default_headers and per-call headers."""

    def _make(responses, **kwargs):
        client, transport = make_client(
            responses, default_headers={"Authorization": f"bearer {FAKE_TOKEN}"}, **kwargs
        )
        return client, transport

    return _make


@pytest.mark.parametrize("code", [400, 401, 403, 404, 422])
def test_non_retryable_error_message_has_no_auth_values(
    per_request_and_default, caplog, code
):
    client, transport = per_request_and_default([status(code)])
    caplog.set_level(logging.DEBUG)
    with pytest.raises(HttpError) as exc:
        client.get(URL, headers=AUTH_HEADERS)
    # Sanity: the secret really was sent, so the check below is meaningful.
    assert transport.requests[0].headers["X-API-Key"] == FAKE_KEY
    _assert_clean(str(exc.value))
    _assert_clean(repr(exc.value))
    _assert_clean(caplog.text)


def test_retries_exhausted_message_and_logs_have_no_auth_values(
    per_request_and_default, caplog
):
    client, _ = per_request_and_default([status(503)] * 3, max_retries=2)
    caplog.set_level(logging.DEBUG)
    with pytest.raises(RateLimitExceeded) as exc:
        client.post_json(URL, {"q": "x"}, headers=AUTH_HEADERS)
    assert "retries exhausted" in str(exc.value)
    assert caplog.records, "retry warnings expected"
    _assert_clean(str(exc.value))
    _assert_clean(caplog.text)


def test_network_errors_exhausted_message_and_logs_have_no_auth_values(
    per_request_and_default, caplog
):
    client, _ = per_request_and_default(
        [urllib.error.URLError("connection refused")] * 2, max_retries=1
    )
    caplog.set_level(logging.DEBUG)
    with pytest.raises(HttpError) as exc:
        client.get(URL, headers=AUTH_HEADERS)
    assert exc.value.status == 0
    _assert_clean(str(exc.value))
    _assert_clean(caplog.text)


def test_quota_exhausted_message_and_logs_have_no_auth_values(
    per_request_and_default, caplog
):
    client, transport = per_request_and_default(
        [status(429, {"Retry-After": "86400"})], max_wait=60
    )
    caplog.set_level(logging.DEBUG)
    with pytest.raises(QuotaExhausted) as exc:
        client.post_form(URL, {"grant_type": "client_credentials"}, headers=AUTH_HEADERS)
    assert len(transport.requests) == 1
    _assert_clean(str(exc.value))
    _assert_clean(caplog.text)


def test_defer_too_long_message_has_no_auth_values(per_request_and_default, caplog):
    client, _ = per_request_and_default([])
    caplog.set_level(logging.DEBUG)
    with pytest.raises(RateLimitExceeded) as exc:
        client.defer(10_000)
    _assert_clean(str(exc.value))
    _assert_clean(caplog.text)
