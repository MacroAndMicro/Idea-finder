from __future__ import annotations

import io

import pytest

from scrapers import pipeline
from scrapers.config import MissingSecretError
from scrapers.http_client import HttpError

ALL_KEYS = ("GITHUB_TOKEN", "STACKEXCHANGE_KEY", "REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET",
            "REDDIT_USER_AGENT")


class Recorder:
    def __init__(self, codes=None, crash=()):
        self.calls: list[tuple[str, list[str]]] = []
        self.codes = codes or {}
        self.crash = set(crash)

    def stage(self, name):
        def _run(argv, out):
            key = f"{name}:{argv[1]}" if name == "ingest" else name
            self.calls.append((key, list(argv)))
            if key in self.crash:
                raise RuntimeError("boom SECRETVALUE")
            return self.codes.get(key, 0)
        return _run

    def stages(self):
        return {n: self.stage(n) for n in ("ingest", "extract", "embed", "synthesize")}


@pytest.fixture(autouse=True)
def _no_supabase_backlog(monkeypatch):
    def _missing():
        raise MissingSecretError("SUPABASE_URL")
    monkeypatch.setattr(pipeline, "_default_backlog", _missing)


@pytest.fixture
def keys(monkeypatch):
    for k in ALL_KEYS:
        monkeypatch.setenv(k, "x")
    return monkeypatch


def run(argv, rec):
    out = io.StringIO()
    return pipeline.run(argv, stages=rec.stages(), out=out), out.getvalue()


def test_runs_stages_in_order_with_extract_cap(keys):
    rec = Recorder()
    code, out = run(["--sources", "hackernews,github", "--extract-limit", "7"], rec)
    assert code == 0
    assert [c[0] for c in rec.calls] == ["ingest:hackernews", "ingest:github", "extract",
                                         "embed", "synthesize"]
    assert rec.calls[2][1] == ["--limit", "7", "--batch-size", "8", "--max-requests", "18"]
    assert rec.calls[4][1] == ["--limit", "2"]
    assert "pipeline status=success stages=5 ok=5 failed=0 skipped=0" in out


def test_source_failure_does_not_stop_other_stages(keys):
    rec = Recorder(codes={"ingest:github": 1}, crash={"embed"})
    code, out = run(["--sources", "github,hackernews"], rec)
    assert code == 1
    assert [c[0] for c in rec.calls] == ["ingest:github", "ingest:hackernews", "extract",
                                         "embed", "synthesize"]
    assert "stage=ingest:github status=failed exit=1" in out
    assert "stage=embed status=failed crashed (RuntimeError)" in out
    assert "SECRETVALUE" not in out
    assert "ok=3 failed=2" in out


def test_sources_with_missing_secrets_are_skipped(keys):
    keys.delenv("REDDIT_CLIENT_ID")
    keys.delenv("STACKEXCHANGE_KEY")
    rec = Recorder()
    code, out = run([], rec)
    assert code == 0
    ingested = [c[0] for c in rec.calls if c[0].startswith("ingest")]
    assert ingested == ["ingest:hackernews", "ingest:github"]
    assert "stage=ingest:reddit status=skipped missing REDDIT_CLIENT_ID" in out
    assert "stage=ingest:stackexchange status=skipped missing STACKEXCHANGE_KEY" in out
    assert "skipped=2" in out


def test_dry_run_and_skip_synthesize(keys):
    rec = Recorder()
    code, out = run(["--sources", "hackernews", "--dry-run", "--skip-synthesize"], rec)
    assert code == 0
    assert rec.calls[0] == ("ingest:hackernews", ["--source", "hackernews", "--dry-run"])
    assert rec.calls[1][0] == "extract" and rec.calls[1][1][-1] == "--dry-run"
    assert rec.calls[2] == ("embed", ["--dry-run"]) and len(rec.calls) == 3
    assert "stage=synthesize status=skipped --skip-synthesize" in out


def test_dry_run_passes_to_synthesize(keys):
    rec = Recorder()
    run(["--sources", "hackernews", "--dry-run"], rec)
    assert rec.calls[-1] == ("synthesize", ["--dry-run"])


def test_rejects_unknown_source_and_bad_limit(keys):
    with pytest.raises(SystemExit):
        run(["--sources", "g2"], Recorder())
    with pytest.raises(SystemExit):
        run(["--extract-limit", "0"], Recorder())


def test_stage_argparse_exit_counts_as_failure(keys):
    def bad(argv, out):
        raise SystemExit(2)

    out = io.StringIO()
    rec = Recorder()
    code = pipeline.run(["--sources", "hackernews"], stages={**rec.stages(), "extract": bad},
                        out=out)
    assert code == 1 and "stage=extract status=failed exit=2" in out.getvalue()


def test_default_extract_budget_fits_free_tier(keys):
    rec = Recorder()
    run(["--sources", "hackernews"], rec)
    argv = dict(zip(rec.calls[1][1][::2], rec.calls[1][1][1::2], strict=True))
    assert argv == {"--limit": "112", "--batch-size": "8", "--max-requests": "18"}
    assert pipeline.DEFAULT_EXTRACT_MAX_REQUESTS + pipeline.DEFAULT_SYNTHESIZE_LIMIT == 20


# ---- IF-65 backlog report ----

def _sig(i, src, processed=False):
    return {"id": i, "source_platform": src,
            "processed_at": "2026-11-18T00:00:00+00:00" if processed else None}


def test_days_to_clear():
    assert pipeline.days_to_clear(0, 112) == 0
    assert pipeline.days_to_clear(1, 112) == 1
    assert pipeline.days_to_clear(112, 112) == 1
    assert pipeline.days_to_clear(113, 112) == 2
    assert pipeline.days_to_clear(5, 0) is None


def test_backlog_rows_per_source_and_total():
    signals = [_sig(1, "github", True), _sig(2, "github", True), _sig(3, "github"),
               _sig(4, "hackernews"), _sig(5, "hackernews"), _sig(6, "stackexchange", True)]
    rows = pipeline.backlog_rows(signals, {1, 6}, per_day=2)
    by = {r.source: r for r in rows}
    assert [r.source for r in rows] == ["github", "hackernews", "stackexchange", "total"]
    assert by["github"] == pipeline.BacklogRow("github", 3, 1, 1, 1, 1)
    assert by["hackernews"] == pipeline.BacklogRow("hackernews", 2, 0, 0, 2, 1)
    assert by["stackexchange"].unprocessed == 0 and by["stackexchange"].days_to_clear == 0
    assert by["total"] == pipeline.BacklogRow("total", 6, 2, 1, 3, 2)
    assert pipeline.backlog_rows([], set(), 2) == []


def test_pipeline_prints_backlog_lines(keys):
    out = io.StringIO()
    rec = Recorder()
    code = pipeline.run(["--sources", "hackernews", "--extract-limit", "10"],
                        stages=rec.stages(),
                        backlog=lambda: ([_sig(i, "hackernews") for i in range(1, 26)], set()),
                        out=out)
    text = out.getvalue()
    assert code == 0
    assert ("backlog source=hackernews ingested=25 extracted=0 skipped=0 unprocessed=25 "
            "days_to_clear=3 per_day=10") in text
    assert "backlog source=total" in text


def test_backlog_read_failure_never_fails_pipeline(keys):
    def boom():
        raise HttpError(503, "https://proj.supabase.co/rest/v1/raw_signals")
    out = io.StringIO()
    code = pipeline.run(["--sources", "hackernews"], stages=Recorder().stages(),
                        backlog=boom, out=out)
    assert code == 0 and "backlog skipped: read failed (HTTP 503)" in out.getvalue()
    _, text = run(["--sources", "hackernews"], Recorder())
    assert "backlog skipped: missing SUPABASE_URL" in text


class _DryStore:
    """Read-only stub for extract + embed; any write fails the test."""

    def fetch_unprocessed_pool(self):
        return [{"id": i, "source_platform": "github", "title": f"CSV export broken {i}",
                 "body": "We export CSV by hand every week, costs hours.", "tags": []}
                for i in range(1, 10)]

    def fetch_signals_to_embed(self, limit, *, pain_only=True):
        return [{"id": 1, "title": "t", "body": "b"}]

    def __getattr__(self, name):  # save_extraction, mark_processed, save_signal_embedding
        raise AssertionError(f"dry run must not write: {name}")


def test_dry_run_makes_zero_provider_calls_end_to_end(keys):
    """IF-85: real extract/embed stages with fake providers — 0 requests under --dry-run."""
    from scrapers import embed, extract
    from scrapers.llm.fake import FakeEmbeddingClient, FakeLLMClient

    llm = FakeLLMClient()
    embedded: list[int] = []

    class _Embedder(FakeEmbeddingClient):
        def _embed(self, texts):
            embedded.append(len(texts))
            return super()._embed(texts)

    store = _DryStore()
    stages = {
        "ingest": lambda argv, out: 0,
        "extract": lambda argv, out: extract.run(
            argv, llm_factory=lambda: llm, store_factory=lambda: store, out=out),
        "embed": lambda argv, out: embed.run(
            argv, embedder_factory=_Embedder, store_factory=lambda: store, out=out),
    }
    out = io.StringIO()
    code = pipeline.run(["--sources", "hackernews", "--dry-run", "--skip-synthesize"],
                        stages=stages, out=out)
    text = out.getvalue()
    assert code == 0, text
    assert llm.calls == [] and embedded == []
    assert "stage=extract status=ok" in text and "stage=embed status=ok" in text
    assert "extract mode=dry-run" in text and "embed mode=dry-run" in text
