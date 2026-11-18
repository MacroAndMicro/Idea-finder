import base64
import io
from datetime import UTC, datetime

import pytest

from scrapers import ingest
from scrapers.adapters.reddit import RedditAdapter
from scrapers.http_client import HttpResponse, RateLimitExceeded
from scrapers.tests.helpers import load_fixture, ok

SINCE = datetime(2025, 11, 10, tzinfo=UTC)
UA = "linux:idea-finder-test:0.1 (by /u/idea_finder_test)"


def fx(name, headers=None):
    return ok(load_fixture(f"reddit/{name}"), headers)


def adapter(client, clock, **kw):
    return RedditAdapter("cid", "csecret", UA, client, clock=clock.time, **kw)


def test_oauth_token_then_search_maps_posts(make_client, clock):
    client, transport = make_client([fx("token.json"), fx("search_page1.json"),
                                     fx("search_page2_reaches_since.json")])
    signals = list(adapter(client, clock, subreddits=["sysadmin"], max_pages=3)
                   .fetch("workaround", SINCE))
    # p3 is NSFW (skipped); p5 is older than since → stop, no third page.
    assert [s.external_id for s in signals] == ["t3_p1", "t3_p2", "t3_p4"]
    first = signals[0]
    assert first.source_platform == "reddit"
    assert first.url == "https://www.reddit.com/r/sysadmin/comments/p1/some_title/"
    assert first.body.startswith("We export CSVs") and first.tags == ["sysadmin", "Question"]
    assert first.score == 12 and first.comment_count == 5
    assert first.author_handle_hash and "user_p1" not in first.author_handle_hash
    assert signals[1].author_handle_hash is None and signals[1].body is None
    token_req, search1, search2 = transport.requests
    assert token_req.method == "POST"
    assert token_req.url == "https://www.reddit.com/api/v1/access_token"
    assert token_req.body == b"grant_type=client_credentials"
    basic = base64.b64encode(b"cid:csecret").decode()
    assert token_req.headers["Authorization"] == f"Basic {basic}"
    assert search1.url.startswith("https://oauth.reddit.com/r/sysadmin/search?")
    assert "restrict_sr=1" in search1.url and "sort=new" in search1.url
    assert "after" not in search1.url and "after=t3_p3" in search2.url
    assert search1.headers["Authorization"] == "bearer FAKE_TOKEN"
    assert all(r.headers["User-Agent"] == UA for r in transport.requests)
    assert all("www.reddit.com" not in r.url for r in transport.requests[1:])


def test_token_is_reused_across_subreddits(make_client, clock):
    client, transport = make_client([fx("token.json"), fx("empty.json"), fx("empty.json")])
    list(adapter(client, clock, subreddits=["devops", "SaaS"]).fetch("q", SINCE))
    assert [r.method for r in transport.requests] == ["POST", "GET", "GET"]
    assert "/r/SaaS/search" in transport.requests[2].url


def test_rate_limit_headers_defer_next_request(make_client, clock):
    hdrs = {"X-Ratelimit-Remaining": "0.0", "X-Ratelimit-Reset": "30", "X-Ratelimit-Used": "100"}
    client, _ = make_client([fx("token.json"), fx("empty.json", hdrs), fx("empty.json")])
    list(adapter(client, clock, subreddits=["devops", "SaaS"]).fetch("q", SINCE))
    assert 31.0 in clock.sleeps


def test_429_backs_off_then_gives_up(make_client, clock):
    limited = HttpResponse(429, {"X-Ratelimit-Remaining": "0", "X-Ratelimit-Reset": "5"},
                           load_fixture("reddit/rate_limited_429.json"))
    client, _ = make_client([fx("token.json"), limited, limited, limited], max_retries=2)
    with pytest.raises(RateLimitExceeded):
        list(adapter(client, clock, subreddits=["devops"]).fetch("q", SINCE))
    assert clock.sleeps[:2] == [6.0, 6.0]


def test_bad_token_response_raises_without_echo(make_client, clock):
    client, _ = make_client([ok({"error": "invalid_grant csecret"})])
    with pytest.raises(Exception) as exc:
        list(adapter(client, clock, subreddits=["devops"]).fetch("q", SINCE))
    assert "csecret" not in str(exc.value)


def test_invalid_subreddit_name_rejected(make_client, clock):
    client, _ = make_client([])
    with pytest.raises(ValueError):
        adapter(client, clock, subreddits=["../api"])


def test_from_env_reads_subreddits(monkeypatch):
    monkeypatch.setenv("REDDIT_CLIENT_ID", "a")
    monkeypatch.setenv("REDDIT_CLIENT_SECRET", "b")
    monkeypatch.setenv("REDDIT_USER_AGENT", UA)
    monkeypatch.setenv("REDDIT_SUBREDDITS", "sysadmin, devops")
    assert RedditAdapter.from_env().subreddits == ("sysadmin", "devops")
    assert RedditAdapter.missing_env() == []


def test_ingest_reddit_without_keys_exits_2_and_writes_nothing(monkeypatch):
    for name in ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USER_AGENT"):
        monkeypatch.delenv(name, raising=False)

    def no_store():
        raise AssertionError("store must not be opened")

    out = io.StringIO()
    code = ingest.run(["--source", "reddit"], store_factory=no_store, out=out)
    assert code == 2
    assert "REDDIT_CLIENT_ID" in out.getvalue()
    assert set(RedditAdapter.missing_env()) == {"REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET",
                                                 "REDDIT_USER_AGENT"}


def test_time_filter_covers_since(make_client, clock):
    from datetime import timedelta

    client, _ = make_client([])
    a = adapter(client, clock)
    now = datetime.fromtimestamp(clock.now, tz=UTC)
    assert a.time_filter(now - timedelta(days=14)) == "month"
    assert a.time_filter(now - timedelta(days=5)) == "week"
    assert a.time_filter(now - timedelta(days=90)) == "year"
    assert a.time_filter(now - timedelta(days=900)) == "all"
