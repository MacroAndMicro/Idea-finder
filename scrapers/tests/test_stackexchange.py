import logging
from datetime import UTC, datetime

from scrapers.adapters.stackexchange import StackExchangeAdapter
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
