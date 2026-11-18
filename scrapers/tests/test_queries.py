from __future__ import annotations

import re

import pytest

from scrapers import ingest
from scrapers.adapters.reddit import DEFAULT_SUBREDDITS
from scrapers.adapters.stackexchange import DEFAULT_SITES


def test_every_adapter_has_queries_and_no_unknown_source():
    cfg = ingest.load_queries()
    assert set(cfg) == set(ingest.ADAPTERS)
    for source, entry in cfg.items():
        assert entry.queries, source


def test_every_list_entry_has_a_comment():
    lines = ingest.QUERIES_FILE.read_text(encoding="utf-8").splitlines()
    entries = [ln for ln in lines if re.match(r'^\s*"', ln)]
    assert entries
    assert all(re.search(r'",?\s+#\s*\S', ln) for ln in entries), [
        ln for ln in entries if "#" not in ln]


def test_existing_defaults_kept_and_few_additions():
    old = {"hackernews": {"workaround", "is there a tool", "spreadsheet"},
           "github": {"workaround", "feature request integration"},
           "stackexchange": {"workaround", "export"},
           "reddit": {"workaround", "is there a tool", "spreadsheet"}}
    cfg = ingest.load_queries()
    added = 0
    for source, queries in old.items():
        assert queries <= set(cfg[source].queries), source
        added += len(set(cfg[source].queries) - queries)
    assert added <= 5
    assert cfg["stackexchange"].lists["sites"] == DEFAULT_SITES
    assert cfg["reddit"].lists["subreddits"] == DEFAULT_SUBREDDITS


def write(tmp_path, text):
    p = tmp_path / "q.toml"
    p.write_text(text, encoding="utf-8")
    return p


BASE = "".join(f'[{s}]\nqueries = ["x"]\n' for s in ("hackernews", "github", "stackexchange",
                                                       "reddit"))


def test_loader_accepts_minimal_file(tmp_path):
    assert ingest.load_queries(write(tmp_path, BASE))["github"].queries == ("x",)


@pytest.mark.parametrize("text", [
    BASE + '[g2]\nqueries = ["x"]\n',                       # unknown source (Phase 2)
    BASE.replace('[reddit]\nqueries = ["x"]\n', ""),         # source missing
    BASE.replace('[github]\nqueries = ["x"]', '[github]\nqueries = []'),
    BASE.replace('[github]\nqueries = ["x"]', '[github]\nqueries = [1]'),
    BASE.replace('[github]\nqueries = ["x"]', '[github]\nqueries = ["x"]\nsites = ["a"]'),
])
def test_loader_rejects_bad_files(tmp_path, text):
    with pytest.raises(ingest.QueryConfigError):
        ingest.load_queries(write(tmp_path, text))


def test_adapter_kwargs_respect_env_override(monkeypatch):
    monkeypatch.delenv("STACKEXCHANGE_SITES", raising=False)
    assert ingest.adapter_kwargs("stackexchange") == {"sites": list(DEFAULT_SITES)}
    assert ingest.adapter_kwargs("hackernews") == {}
    monkeypatch.setenv("STACKEXCHANGE_SITES", "dba")
    assert ingest.adapter_kwargs("stackexchange") == {}
