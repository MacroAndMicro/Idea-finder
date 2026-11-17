import logging
from datetime import UTC, datetime

from scrapers.adapters.github import GitHubIssuesAdapter
from scrapers.tests.helpers import load_fixture, ok, status

SINCE = datetime(2026, 11, 1, tzinfo=UTC)


def test_maps_issues_and_skips_pull_requests(make_client):
    client, transport = make_client([ok(load_fixture("github/search_page1.json"))])
    adapter = GitHubIssuesAdapter("tok", client, label="enhancement", min_reactions=5)
    signals = list(adapter.fetch("webhook retries", SINCE))
    assert len(signals) == 1
    sig = signals[0]
    assert sig.external_id == "example-org/example-tool#512"
    assert sig.url == "https://github.com/example-org/example-tool/issues/512"
    assert sig.score == 128 and sig.comment_count == 41
    assert sig.tags == ["enhancement", "integrations"]
    assert sig.source_created_at == datetime(2026, 11, 10, 8, 15, tzinfo=UTC)
    assert sig.author_handle_hash and "example-user" not in sig.author_handle_hash

    req = transport.requests[0]
    assert req.headers["Authorization"] == "Bearer tok"
    assert "is%3Aissue" in req.url and "created%3A%3E2026-11-01" in req.url
    assert "reactions%3A%3E%3D5" in req.url and "label%3A%22enhancement%22" in req.url
    assert "tok" not in req.url  # token only in the header


def test_paginates_until_total_count(make_client):
    item = {
        "repository_url": "https://api.github.com/repos/o/r",
        "html_url": "https://github.com/o/r/issues/1", "number": 1, "title": "t",
        "created_at": "2026-11-10T00:00:00Z", "reactions": {"total_count": 3}, "comments": 0,
    }
    page1 = {"total_count": 150, "items": [{**item, "number": i} for i in range(100)]}
    page2 = {"total_count": 150, "items": [{**item, "number": i} for i in range(100, 150)]}
    client, transport = make_client([ok(page1), ok(page2)])
    signals = list(GitHubIssuesAdapter("tok", client, max_pages=5).fetch("q", SINCE))
    assert len(signals) == 150
    assert len(transport.requests) == 2
    assert "page=2" in transport.requests[1].url


def test_secondary_rate_limit_waits(make_client, clock):
    client, _ = make_client(
        [status(403, {"Retry-After": "60"}), ok(load_fixture("github/search_page1.json"))]
    )
    assert len(list(GitHubIssuesAdapter("tok", client).fetch("q", SINCE))) == 1
    assert clock.sleeps[0] == 60.0


def test_primary_rate_limit_waits_for_reset(make_client, clock):
    reset = int(clock.now) + 20
    client, _ = make_client(
        [
            status(403, {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(reset)}),
            ok(load_fixture("github/search_page1.json")),
        ]
    )
    assert len(list(GitHubIssuesAdapter("tok", client).fetch("q", SINCE))) == 1
    assert clock.sleeps[0] == 21.0


def test_missing_token_skips_with_clear_message(make_client, monkeypatch, caplog):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    client, transport = make_client([])
    with caplog.at_level(logging.WARNING):
        assert list(GitHubIssuesAdapter.from_env(client=client).fetch("q", SINCE)) == []
    assert "GITHUB_TOKEN is not set" in caplog.text
    assert transport.requests == []
