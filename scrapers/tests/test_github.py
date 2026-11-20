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
    assert "is%3Aissue" in req.url and "created%3A%3E%3D2026-11-01T00%3A00%3A00Z" in req.url
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


def test_since_filter_uses_full_utc_instant_not_date():
    # IF-83: created:>2026-11-18 excluded the rest of Nov 18 (e.g. an 11:00Z issue).
    from datetime import timedelta, timezone

    from scrapers.adapters.github import created_filter

    since = datetime(2026, 11, 18, 10, 30, tzinfo=UTC)
    # IF-93: lookback_days=0 isolates the instant formatting from the rolling window.
    q = GitHubIssuesAdapter("tok", lookback_days=0).build_query("webhook", since)
    assert "created:>=2026-11-18T10:30:00Z" in q
    assert "created:>2026-11-18 " not in q + " "
    # the instant compares correctly against an item created later that day
    item_created = datetime(2026, 11, 18, 11, 0, tzinfo=UTC)
    assert item_created >= since
    # naive → UTC; other offsets normalised to UTC
    assert created_filter(datetime(2026, 11, 18, 10, 30)) == "created:>=2026-11-18T10:30:00Z"
    cet = timezone(timedelta(hours=1))
    assert created_filter(datetime(2026, 11, 18, 11, 30, tzinfo=cet)) == (
        "created:>=2026-11-18T10:30:00Z"
    )


# --- IF-93: rolling look-back for issue search -------------------------------------------

def _issue(number: int, created: str, reactions: int) -> dict:
    return {
        "repository_url": "https://api.github.com/repos/o/r",
        "html_url": f"https://github.com/o/r/issues/{number}", "number": number,
        "title": f"t{number}", "created_at": created,
        "reactions": {"total_count": reactions}, "comments": 0,
    }


def test_rolling_lookback_matches_older_issue_that_gained_reactions(make_client):
    # Last success was 4h ago; an issue created 3 days ago with 5 reactions must still be
    # in the search window (before IF-93 the window was only the last ~4h).
    from scrapers.adapters.github import issue_window_start

    now = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
    since = datetime(2026, 11, 20, 8, 0, tzinfo=UTC)
    issue_created = datetime(2026, 11, 17, 12, 0, tzinfo=UTC)
    start = issue_window_start(since, now, 14)
    assert start == datetime(2026, 11, 6, 12, 0, tzinfo=UTC)
    assert issue_created >= start

    adapter = GitHubIssuesAdapter("tok", None, now=lambda: now)
    q = adapter.build_query("webhook", since)
    assert "created:>=2026-11-06T12:00:00Z" in q and "reactions:>=3" in q

    client, transport = make_client(
        [ok({"total_count": 1, "items": [_issue(7, "2026-11-17T12:00:00Z", 5)]})])
    adapter = GitHubIssuesAdapter("tok", client, now=lambda: now)
    signals = list(adapter.fetch("webhook", since))
    assert [s.external_id for s in signals] == ["o/r#7"] and signals[0].score == 5
    assert "created%3A%3E%3D2026-11-06T12%3A00%3A00Z" in transport.requests[0].url


def test_window_keeps_older_since_and_can_be_disabled():
    from scrapers.adapters.github import issue_window_start

    now = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
    old = datetime(2026, 10, 1, tzinfo=UTC)
    assert issue_window_start(old, now, 14) == old  # --since-days 50 still wins
    recent = datetime(2026, 11, 20, 8, 0)  # naive → UTC
    assert issue_window_start(recent, now, 0) == recent.replace(tzinfo=UTC)
    q = GitHubIssuesAdapter("tok", None, lookback_days=0, now=lambda: now).build_query(
        "x", recent)
    assert "created:>=2026-11-20T08:00:00Z" in q


def test_lookback_env(monkeypatch, caplog):
    from scrapers.adapters.github import (
        DEFAULT_ISSUE_LOOKBACK_DAYS,
        GitHubAdapter,
        issue_lookback_from_env,
    )

    monkeypatch.delenv("GITHUB_ISSUE_LOOKBACK_DAYS", raising=False)
    assert issue_lookback_from_env() == DEFAULT_ISSUE_LOOKBACK_DAYS == 14
    monkeypatch.setenv("GITHUB_ISSUE_LOOKBACK_DAYS", "30")
    assert issue_lookback_from_env() == 30
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    assert GitHubAdapter.from_env().issues.lookback_days == 30
    for bad in ("-1", "two"):
        monkeypatch.setenv("GITHUB_ISSUE_LOOKBACK_DAYS", bad)
        with caplog.at_level(logging.WARNING):
            assert issue_lookback_from_env() == DEFAULT_ISSUE_LOOKBACK_DAYS
    assert "GITHUB_ISSUE_LOOKBACK_DAYS" in caplog.text and "-1" not in caplog.text


def test_issue_queries_round_robin_within_page_budget(make_client):
    # A multi-day window must not let the first query fill --limit on its own.
    page_a = {"total_count": 2, "items": [_issue(1, "2026-11-19T00:00:00Z", 4),
                                          _issue(2, "2026-11-18T00:00:00Z", 4)]}
    page_b = {"total_count": 1, "items": [_issue(3, "2026-11-19T00:00:00Z", 9)]}
    client, transport = make_client([ok(page_a), ok(page_b)])
    adapter = GitHubIssuesAdapter("tok", client, max_pages=3)
    ids = [s.external_id for s in adapter.fetch_all(["a", "b"], SINCE)]
    assert ids == ["o/r#1", "o/r#3", "o/r#2"]
    assert len(transport.requests) == 2  # one page per query, no extra calls
