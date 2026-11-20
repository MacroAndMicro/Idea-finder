import itertools
import logging
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

from scrapers.adapters.base import rolling_window_start as window_start
from scrapers.adapters.stackexchange import (
    DEFAULT_LOOKBACK_DAYS,
    StackExchangeAdapter,
    lookback_from_env,
)
from scrapers.http_client import HttpResponse
from scrapers.store import SupabaseStore
from scrapers.tests.helpers import load_fixture, ok

SINCE = datetime(2026, 11, 1, tzinfo=UTC)


def _gz(name):
    return ok(load_fixture(f"stackexchange/{name}"), gz=True)  # SE always gzips


def test_maps_questions_from_gzip(make_client):
    client, transport = make_client([_gz("search_page1.json"), _gz("search_page2_low_quota.json")])
    adapter = StackExchangeAdapter("k", client, sites=["stackoverflow"], max_pages=2)
    signals = list(adapter.fetch("csv merge", SINCE))
    assert [s.external_id for s in signals] == ["stackoverflow:79900001", "stackoverflow:79900002"]
    sig = signals[0]
    assert sig.title.startswith("How do I merge weekly CSV exports")
    assert sig.body == "Every Monday I export & merge by hand.\nvlookup..."
    assert sig.score == 15 and sig.comment_count == 2
    assert sig.tags == ["excel", "power-query", "csv"]
    assert sig.author_handle_hash and "12345" not in sig.author_handle_hash
    assert signals[1].author_handle_hash is None  # deleted user
    url = transport.requests[0].url
    assert "site=stackoverflow" in url and f"fromdate={int(SINCE.timestamp())}" in url
    assert "filter=withbody" in url


def test_backoff_field_is_honored_before_next_request(make_client, clock):
    client, _ = make_client([_gz("search_page1.json"), _gz("search_page2_low_quota.json")])
    list(StackExchangeAdapter("k", client, sites=["stackoverflow"], max_pages=2).fetch("q", SINCE))
    assert clock.sleeps and abs(clock.sleeps[0] - 10.0) < 1e-6


def test_stops_when_quota_low(make_client):
    # page2 reports quota_remaining=20 (< floor 50) → no requests for the next site.
    client, transport = make_client([_gz("search_page2_low_quota.json")])
    adapter = StackExchangeAdapter("k", client, sites=["serverfault", "superuser"], max_pages=3)
    signals = list(adapter.fetch("cron", SINCE))
    assert len(signals) == 1
    assert len(transport.requests) == 1
    assert adapter.quota_remaining == 20


def test_missing_key_skips_with_clear_message(make_client, monkeypatch, caplog):
    monkeypatch.delenv("STACKEXCHANGE_KEY", raising=False)
    client, transport = make_client([])
    with caplog.at_level(logging.WARNING):
        assert list(StackExchangeAdapter.from_env(client=client).fetch("q", SINCE)) == []
    assert "STACKEXCHANGE_KEY is not set" in caplog.text
    assert transport.requests == []


def test_site_list_from_env(monkeypatch):
    monkeypatch.setenv("STACKEXCHANGE_SITES", "askubuntu, dba")
    assert StackExchangeAdapter.from_env().sites == ("askubuntu", "dba")


# --- IF-94: rolling look-back window, activity sort, (query, site) interleave ---------

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
RECENT = NOW - timedelta(hours=4)  # what choose_since returns ~4h after the last run


def _page(*items, has_more=False, quota=9000):
    return ok({"items": list(items), "has_more": has_more, "quota_remaining": quota}, gz=True)


def _q(qid, score=1):
    return {"question_id": qid, "link": f"https://stackoverflow.com/q/{qid}",
            "title": f"t{qid}", "body": "<p>b</p>", "score": score, "creation_date": 1763000000}


def _params(request):
    return parse_qs(urlparse(request.url).query)


def test_window_start_uses_earlier_of_since_and_lookback():
    assert window_start(RECENT, NOW, 14) == NOW - timedelta(days=14)
    old = NOW - timedelta(days=30)
    assert window_start(old, NOW, 14) == old  # a longer --since-days window still wins
    assert window_start(RECENT, NOW, 0) == RECENT  # 0 disables the rolling window
    naive = datetime(2026, 11, 20, 8, 0)
    assert window_start(naive, NOW, 0).tzinfo is UTC


def test_fetch_sends_rolling_fromdate_and_activity_sort(make_client):
    client, transport = make_client([_page(_q(1))])
    adapter = StackExchangeAdapter("k", client, sites=["stackoverflow"], now=lambda: NOW)
    assert len(list(adapter.fetch("workaround", RECENT))) == 1
    params = _params(transport.requests[0])
    assert params["fromdate"] == [str(int((NOW - timedelta(days=14)).timestamp()))]
    assert params["sort"] == ["activity"] and params["order"] == ["desc"]


def test_negative_score_questions_are_dropped(make_client):
    client, _ = make_client([_page(_q(1, score=-2), _q(2, score=0), _q(3, score=7))])
    adapter = StackExchangeAdapter("k", client, sites=["stackoverflow"], now=lambda: NOW)
    assert [s.external_id for s in adapter.fetch("q", RECENT)] == [
        "stackoverflow:2", "stackoverflow:3"]


def test_fetch_all_interleaves_query_site_pairs(make_client):
    # Each (query, site) stream gets its first page before any stream gets a second item.
    client, transport = make_client([
        _page(_q(1), _q(2)), _page(_q(10)), _page(_q(20)), _page(_q(30)),
    ])
    adapter = StackExchangeAdapter("k", client, sites=["stackoverflow", "serverfault"],
                                   now=lambda: NOW)
    signals = list(itertools.islice(adapter.fetch_all(["a", "b"], RECENT), 4))
    assert [s.external_id for s in signals] == [
        "stackoverflow:1", "serverfault:10", "stackoverflow:20", "serverfault:30"]
    pairs = [(_params(r)["q"][0], _params(r)["site"][0]) for r in transport.requests]
    assert pairs == [("a", "stackoverflow"), ("a", "serverfault"),
                     ("b", "stackoverflow"), ("b", "serverfault")]


def test_fetch_all_still_stops_on_low_quota(make_client):
    client, transport = make_client([_page(_q(1), quota=10)])
    adapter = StackExchangeAdapter("k", client, sites=["stackoverflow", "superuser"],
                                   now=lambda: NOW)
    assert len(list(adapter.fetch_all(["a", "b"], RECENT))) == 1
    assert len(transport.requests) == 1  # every other stream sees quota < floor


def test_fetch_all_without_key_makes_no_request(make_client):
    client, transport = make_client([])
    assert list(StackExchangeAdapter(None, client).fetch_all(["a"], RECENT)) == []
    assert transport.requests == []


def test_lookback_from_env(monkeypatch, caplog):
    monkeypatch.delenv("STACKEXCHANGE_LOOKBACK_DAYS", raising=False)
    assert lookback_from_env() == DEFAULT_LOOKBACK_DAYS == 14
    monkeypatch.setenv("STACKEXCHANGE_LOOKBACK_DAYS", "7")
    assert lookback_from_env() == 7
    assert StackExchangeAdapter.from_env().lookback_days == 7
    monkeypatch.setenv("STACKEXCHANGE_LOOKBACK_DAYS", "0")
    assert lookback_from_env() == 0
    with caplog.at_level(logging.WARNING):
        for bad in ("-1", "two weeks", "1.5"):
            monkeypatch.setenv("STACKEXCHANGE_LOOKBACK_DAYS", bad)
            assert lookback_from_env() == DEFAULT_LOOKBACK_DAYS
    assert "STACKEXCHANGE_LOOKBACK_DAYS must be an integer >= 0" in caplog.text


def test_reseen_question_is_not_reinserted(make_client):
    # Two runs with overlapping 14-day windows see the same question: same external_id,
    # and the store's ignore-duplicates upsert reports it as skipped, not inserted.
    first, _ = make_client([_page(_q(5)), _page(_q(5))])
    adapter = StackExchangeAdapter("k", first, sites=["stackoverflow"], now=lambda: NOW)
    run1 = list(adapter.fetch("q", RECENT))
    run2 = list(adapter.fetch("q", RECENT))
    assert run1[0].external_id == run2[0].external_id == "stackoverflow:5"
    store_client, transport = make_client([
        HttpResponse(201, {}, b'[{"id": 1}]'), HttpResponse(201, {}, b"[]")])
    store = SupabaseStore("https://proj.supabase.co/", "secret", store_client)
    assert store.upsert_signals(run1).inserted == 1
    second = store.upsert_signals(run2)
    assert (second.inserted, second.skipped) == (0, 1)
    assert all("resolution=ignore-duplicates" in r.headers["Prefer"] for r in transport.requests)
