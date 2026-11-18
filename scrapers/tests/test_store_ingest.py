from __future__ import annotations

import io
import json
from datetime import UTC, datetime

import pytest

from scrapers import ingest
from scrapers.adapters.base import SourceAdapter
from scrapers.http_client import HttpResponse
from scrapers.models import RawSignal
from scrapers.store import SupabaseStore
from scrapers.tests.helpers import ok, status

SECRET = "service-role-secret-value"


def sig(i: int, platform: str = "hackernews") -> RawSignal:
    return RawSignal(platform, str(i), f"https://example.test/{i}", title=f"t{i}", body="b",
                     author_handle_hash="h" * 64)


def created(n: int) -> HttpResponse:
    return HttpResponse(201, {}, json.dumps([{"id": i} for i in range(n)]).encode())


def make_store(make_client, responses):
    client, transport = make_client(responses)
    return SupabaseStore("https://proj.supabase.co/", SECRET, client), transport


def test_upsert_posts_rows_with_ignore_duplicates(make_client):
    store, transport = make_store(make_client, [created(2)])
    result = store.upsert_signals([sig(1), sig(2), sig(3)])
    assert (result.received, result.inserted, result.skipped) == (3, 2, 1)
    req = transport.requests[0]
    assert req.method == "POST"
    assert req.url == ("https://proj.supabase.co/rest/v1/raw_signals"
                       "?on_conflict=source_platform,external_id&select=id")
    assert "resolution=ignore-duplicates" in req.headers["Prefer"]
    assert req.headers["apikey"] == SECRET
    rows = json.loads(req.body)
    assert [r["external_id"] for r in rows] == ["1", "2", "3"]
    # Only the hash is stored, never a raw username field.
    assert all("author" not in k or k == "author_handle_hash" for r in rows for k in r)


def test_upsert_batches_and_dedupes_within_run(make_client):
    store, transport = make_store(make_client, [created(2), created(1)])
    result = store.upsert_signals([sig(1), sig(1), sig(2), sig(3)], batch_size=2)
    assert len(transport.requests) == 2
    assert (result.received, result.inserted, result.skipped) == (4, 3, 1)


def test_upsert_empty_makes_no_request(make_client):
    store, transport = make_store(make_client, [])
    assert store.upsert_signals([]).received == 0
    assert transport.requests == []


def test_record_run_skips_when_table_missing(make_client):
    store, transport = make_store(make_client, [status(404)])
    assert store.record_run({"status": "success"}) is False
    assert len(transport.requests) == 1


def test_record_run_writes_when_table_exists(make_client):
    store, transport = make_store(make_client, [ok(b"[]"), HttpResponse(201, {}, b"")])
    assert store.record_run({"status": "success"}) is True
    assert transport.requests[1].url.endswith("/rest/v1/ingestion_runs")


def test_record_run_tolerates_schema_mismatch(make_client):
    store, _ = make_store(make_client, [ok(b"[]"), status(400)])
    assert store.record_run({"unknown_col": 1}) is False


def test_from_env_requires_vars(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    with pytest.raises(Exception, match="SUPABASE_URL"):
        SupabaseStore.from_env()


class StubAdapter(SourceAdapter):
    platform = "hackernews"

    def __init__(self, per_query: dict[str, list[RawSignal]]) -> None:
        self.per_query = per_query
        self.calls: list[str] = []

    def fetch(self, query, since):
        self.calls.append(query)
        yield from self.per_query.get(query, [])


class StubStore:
    def __init__(self):
        self.signals: list[RawSignal] = []
        self.runs: list[dict] = []

    def upsert_signals(self, signals):
        from scrapers.store import StoreResult
        self.signals = list(signals)
        return StoreResult(len(self.signals), len(self.signals) - 1, 1)

    def record_run(self, row):
        self.runs.append(row)
        return True


NOW = datetime(2026, 11, 17, tzinfo=UTC)


def run_cli(argv, adapter, store=None):
    out = io.StringIO()
    code = ingest.run(argv, adapter_factory=lambda s: adapter,
                      store_factory=lambda: store, now=lambda: NOW, out=out)
    return code, out.getvalue()


def test_cli_stores_dedupes_and_limits():
    adapter = StubAdapter({"a": [sig(1), sig(2)], "b": [sig(2), sig(3), sig(4)]})
    store = StubStore()
    code, out = run_cli(["--source", "hackernews", "--query", "a", "--query", "b",
                         "--limit", "3"], adapter, store)
    assert code == 0
    assert [s.external_id for s in store.signals] == ["1", "2", "3"]
    assert "fetched=3 inserted=2 skipped=1 status=success" in out
    assert store.runs[0]["fetched_count"] == 3
    assert SECRET not in out


def test_cli_dry_run_writes_nothing():
    adapter = StubAdapter({"x": [sig(1)]})

    def no_store():
        raise AssertionError("store must not be created in dry-run")

    out = io.StringIO()
    code = ingest.run(["--source", "hackernews", "--query", "x", "--dry-run"],
                      adapter_factory=lambda s: adapter, store_factory=no_store, out=out)
    assert code == 0
    assert "mode=dry-run fetched=1 inserted=0" in out.getvalue()


def test_cli_uses_default_queries():
    adapter = StubAdapter({})
    run_cli(["--source", "hackernews"], adapter, StubStore())
    assert tuple(adapter.calls) == ingest.DEFAULT_QUERIES["hackernews"]


def test_cli_missing_supabase_env_names_variable(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    out = io.StringIO()
    code = ingest.run(["--source", "hackernews"], adapter_factory=lambda s: StubAdapter({}),
                      out=out)
    assert code == 2
    assert "SUPABASE_URL" in out.getvalue()


def test_cli_http_error_reports_failure():
    from scrapers.http_client import HttpError

    class Boom(StubAdapter):
        def fetch(self, query, since):
            raise HttpError(500, "https://api.example.test/x?key=SECRETKEY")
            yield  # pragma: no cover

    store = StubStore()
    code, out = run_cli(["--source", "hackernews"], Boom({}), store)
    assert code == 1
    assert "status=failed" in out and "SECRETKEY" not in out
    assert store.runs[0]["status"] == "Failed"
    assert store.runs[0]["error_summary"] == "fetch hackernews: HTTP 500"


def test_cli_rejects_unknown_source_and_bad_limit():
    with pytest.raises(SystemExit):
        run_cli(["--source", "g2"], StubAdapter({}))
    with pytest.raises(SystemExit):
        run_cli(["--source", "hackernews", "--limit", "0"], StubAdapter({}))


def test_cli_hint_when_key_missing():
    code, out = run_cli(["--source", "github"], StubAdapter({}), StubStore())
    assert code == 0 and "GITHUB_TOKEN" in out


def test_cli_partial_failure_still_stores_fetched():
    from scrapers.http_client import HttpError

    class Half(StubAdapter):
        def fetch(self, query, since):
            yield sig(1)
            raise HttpError(503, "https://api.example.test/x")

    store = StubStore()
    code, out = run_cli(["--source", "hackernews", "--query", "q"], Half({}), store)
    assert code == 1 and "status=partial" in out
    assert [s.external_id for s in store.signals] == ["1"]


RUN_KEYS = {"source_platform", "started_at", "finished_at", "status", "fetched_count",
            "inserted_count", "skipped_count", "error_summary"}


def test_record_run_payload_success():
    store = StubStore()
    run_cli(["--source", "hackernews", "--query", "a"], StubAdapter({"a": [sig(1), sig(2)]}),
            store)
    row = store.runs[0]
    assert set(row) == RUN_KEYS
    assert row == {
        "source_platform": "hackernews", "started_at": NOW.isoformat(),
        "finished_at": NOW.isoformat(), "status": "Success", "fetched_count": 2,
        "inserted_count": 1, "skipped_count": 1, "error_summary": None,
    }


def test_record_run_payload_partial_has_no_url_or_secret():
    from scrapers.http_client import HttpError

    class Half(StubAdapter):
        def fetch(self, query, since):
            yield sig(1)
            raise HttpError(503, "https://api.example.test/x?key=SECRETKEY")

    store = StubStore()
    code, _ = run_cli(["--source", "hackernews", "--query", "q"], Half({}), store)
    row = store.runs[0]
    assert code == 1 and set(row) == RUN_KEYS
    assert row["status"] == "Partial" and row["fetched_count"] == 1
    assert row["error_summary"] == "fetch hackernews: HTTP 503"
    assert "SECRETKEY" not in row["error_summary"] and "http" not in row["error_summary"]


def test_record_run_payload_failed_on_store_error_and_rate_limit():
    from scrapers.http_client import HttpError, RateLimitExceeded

    class BadStore(StubStore):
        def upsert_signals(self, signals):
            raise HttpError(403, "https://proj.supabase.co/rest/v1/raw_signals")

    store = BadStore()
    code, out = run_cli(["--source", "hackernews", "--query", "a"],
                        StubAdapter({"a": [sig(1)]}), store)
    assert code == 1 and "status=failed" in out
    assert store.runs[0]["status"] == "Failed"
    assert store.runs[0]["error_summary"] == "store hackernews: HTTP 403"

    class Limited(StubAdapter):
        def fetch(self, query, since):
            raise RateLimitExceeded(429, "https://api.example.test/x", "retries exhausted")
            yield  # pragma: no cover

    store = StubStore()
    run_cli(["--source", "hackernews"], Limited({}), store)
    assert store.runs[0]["error_summary"] == "fetch hackernews: rate limited (HTTP 429)"


def test_record_run_rejection_logs_warning_without_url(make_client, caplog):
    store, _ = make_store(make_client, [ok(b"[]"), status(400)])
    with caplog.at_level("WARNING"):
        assert store.record_run({"status": "Success"}) is False
    assert "HTTP 400" in caplog.text
    assert "supabase.co" not in caplog.text and SECRET not in caplog.text
