"""IF-74: GitHub Discussions via the official GraphQL API (recorded fixtures, no network)."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from scrapers import ingest
from scrapers.adapters.github import (
    GRAPHQL_URL,
    GitHubAdapter,
    GitHubDiscussionsAdapter,
)
from scrapers.tests.helpers import load_fixture, ok, status

SINCE = datetime(2026, 11, 1, tzinfo=UTC)
LAST_PAGE = {"data": {"search": {"pageInfo": {"hasNextPage": False, "endCursor": None},
                                 "nodes": []}}}


def test_maps_discussions_and_sends_graphql(make_client):
    client, transport = make_client([ok(load_fixture("github/discussions_page1.json")),
                                     ok(LAST_PAGE)])
    signals = list(GitHubDiscussionsAdapter("tok", client).fetch("workaround", SINCE))
    assert len(signals) == 1
    sig = signals[0]
    assert sig.source_platform == "github"
    assert sig.external_id == "discussion:example-org/example-tool#88"
    assert sig.url == "https://github.com/example-org/example-tool/discussions/88"
    assert sig.tags == ["discussion", "Q&A"]
    assert sig.score == 17 and sig.comment_count == 6
    assert "<b>" not in (sig.body or "")
    assert sig.source_created_at == datetime(2026, 11, 9, 12, 30, tzinfo=UTC)
    assert sig.author_handle_hash and "example-user" not in sig.author_handle_hash

    req = transport.requests[0]
    assert req.method == "POST" and req.url == GRAPHQL_URL
    assert req.headers["Authorization"] == "Bearer tok"
    payload = json.loads(req.body)
    assert "type: DISCUSSION" in payload["query"]
    assert payload["variables"]["q"] == "workaround created:>2026-11-01"
    assert payload["variables"]["after"] is None
    # second page follows the cursor
    assert json.loads(transport.requests[1].body)["variables"]["after"] == "Y3Vyc29yOjI="


def test_page_cap_stops_pagination(make_client):
    page = load_fixture("github/discussions_page1.json")
    client, transport = make_client([ok(page), ok(page), ok(page)])
    list(GitHubDiscussionsAdapter("tok", client, max_pages=2).fetch("x", SINCE))
    assert len(transport.requests) == 2


def test_graphql_errors_stop_query_with_warning(make_client, caplog):
    body = {"errors": [{"type": "RATE_LIMITED", "message": "API rate limit exceeded"}]}
    client, transport = make_client([ok(body)])
    with caplog.at_level(logging.WARNING):
        assert list(GitHubDiscussionsAdapter("tok", client).fetch("x", SINCE)) == []
    assert "RATE_LIMITED" in caplog.text and len(transport.requests) == 1


def test_secondary_rate_limit_is_retried(make_client, clock):
    client, transport = make_client([status(403, {"Retry-After": "7"}), ok(LAST_PAGE)])
    start = clock.now
    assert list(GitHubDiscussionsAdapter("tok", client).fetch("x", SINCE)) == []
    assert len(transport.requests) == 2 and clock.now - start >= 7


def test_missing_token_skips(make_client, caplog):
    client, transport = make_client([])
    with caplog.at_level(logging.WARNING):
        assert list(GitHubDiscussionsAdapter(None, client).fetch("x", SINCE)) == []
    assert transport.requests == [] and "GITHUB_TOKEN" in caplog.text


def test_github_source_interleaves_issues_and_discussions(make_client):
    client, transport = make_client([
        ok(load_fixture("github/search_page1.json")),          # issues, query "a"
        ok(load_fixture("github/discussions_page1.json")),     # discussions, query "d"
        ok(LAST_PAGE),
    ])
    adapter = GitHubAdapter("tok", client, discussion_queries=["d"])
    ids = [s.external_id for s in adapter.fetch_all(["a"], SINCE)]
    assert ids == ["example-org/example-tool#512", "discussion:example-org/example-tool#88"]
    assert transport.requests[1].url == GRAPHQL_URL


def test_shared_limit_reaches_discussions(make_client):
    client, transport = make_client([
        ok(load_fixture("github/search_page1.json")),
        ok(load_fixture("github/discussions_page1.json")),
    ])
    adapter = GitHubAdapter("tok", client, discussion_queries=["d"])
    got = list(ingest.collect(adapter, ["a"], SINCE, limit=2))
    assert {s.external_id.startswith("discussion:") for s in got} == {True, False}


def test_discussion_queries_from_toml_and_env(monkeypatch):
    monkeypatch.delenv("GITHUB_DISCUSSION_QUERIES", raising=False)
    cfg = ingest.load_queries()
    assert cfg["github"].lists["discussions"]
    assert ingest.adapter_kwargs("github")["discussion_queries"] == list(
        cfg["github"].lists["discussions"])
    monkeypatch.setenv("GITHUB_DISCUSSION_QUERIES", "one, two")
    assert ingest.adapter_kwargs("github") == {}
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    assert GitHubAdapter.from_env().discussion_queries == ("one", "two")


def test_discussion_http_failure_never_fails_issues(make_client, caplog):
    client, transport = make_client([
        ok(load_fixture("github/search_page1.json")),
        status(403),                                   # GraphQL blocked / forbidden
    ])
    adapter = GitHubAdapter("tok", client, discussion_queries=["d"])
    with caplog.at_level(logging.WARNING):
        ids = [s.external_id for s in adapter.fetch_all(["a"], SINCE)]
    assert ids == ["example-org/example-tool#512"]
    assert "HTTP 403" in caplog.text and "tok" not in caplog.text
