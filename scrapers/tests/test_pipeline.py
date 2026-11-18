from __future__ import annotations

import io

import pytest

from scrapers import pipeline

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
    assert rec.calls[2][1] == ["--limit", "7"]
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
    assert rec.calls == [("ingest:hackernews", ["--source", "hackernews", "--dry-run"]),
                         ("embed", ["--dry-run"])]
    assert "stage=extract status=skipped dry-run" in out
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
