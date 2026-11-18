from __future__ import annotations

import io
import json
import urllib.parse

import pytest

from scrapers import embed
from scrapers.http_client import HttpError, HttpResponse
from scrapers.llm.base import EmbeddingDimensionError
from scrapers.llm.fake import FakeEmbeddingClient
from scrapers.store import SupabaseStore
from scrapers.tests.helpers import ok

SECRET = "service-role-secret-value"


class StubStore:
    def __init__(self, signals):
        self.signals = signals
        self.pain_only = None
        self.saved: list[tuple[int, str, str]] = []

    def fetch_signals_to_embed(self, limit, *, pain_only=True):
        self.pain_only = pain_only
        return self.signals[:limit]

    def save_signal_embedding(self, signal_id, vector, model):
        self.saved.append((signal_id, vector, model))


def sigs(n):
    return [{"id": i, "title": f"title {i}", "body": "body"} for i in range(1, n + 1)]


def run_cli(argv, store, embedder=None):
    out = io.StringIO()
    code = embed.run(argv, embedder_factory=lambda: embedder or FakeEmbeddingClient(),
                     store_factory=lambda: store, out=out)
    return code, out.getvalue()


def test_embeds_in_batches_and_writes_model(monkeypatch):
    monkeypatch.setattr(embed, "BATCH_SIZE", 2)
    store = StubStore(sigs(5))
    code, out = run_cli([], store)
    assert code == 0 and store.pain_only is True
    assert [s[0] for s in store.saved] == [1, 2, 3, 4, 5]
    sid, vec, model = store.saved[0]
    assert model == "fake/fake-embedding"
    assert len(json.loads(vec)) == 1536
    assert "scope=b2b-pain" in out and "embedded=5" in out


class CountingEmbedder(FakeEmbeddingClient):
    def __init__(self):
        super().__init__()
        self.requests = 0

    def _embed(self, texts):
        self.requests += 1
        return super()._embed(texts)


def test_all_flag_dry_run_and_empty_text():
    store = StubStore([{"id": 1, "title": None, "body": None}, *sigs(1)])
    embedder = CountingEmbedder()
    code, out = run_cli(["--all", "--dry-run"], store, embedder)
    assert code == 0 and store.pain_only is False and store.saved == []
    assert embedder.requests == 0  # IF-85: no provider call under --dry-run
    assert "would_embed=1 skipped_empty=1" in out and "scope=all" in out
    assert "requests=0" in out


def test_dry_run_plans_batches_without_calling_provider(monkeypatch):
    monkeypatch.setattr(embed, "BATCH_SIZE", 2)
    store = StubStore(sigs(5))
    embedder = CountingEmbedder()
    code, out = run_cli(["--dry-run"], store, embedder)
    assert code == 0 and embedder.requests == 0 and store.saved == []
    assert "mode=dry-run" in out and "would_embed=5" in out and "planned_requests=3" in out


def test_counting_embedder_counts_real_runs():
    store = StubStore(sigs(1))
    embedder = CountingEmbedder()
    code, _ = run_cli([], store, embedder)
    assert code == 0 and embedder.requests == 1 and len(store.saved) == 1


def test_rejects_wrong_dimensions():
    store = StubStore(sigs(2))
    code, out = run_cli([], store, FakeEmbeddingClient(output_dimensions=768))
    assert code == 1 and store.saved == [] and "768" in out


def test_vector_literal_enforces_1536():
    with pytest.raises(EmbeddingDimensionError):
        embed.vector_literal([0.1] * 3)
    assert embed.vector_literal([0.5] * 1536).startswith("[0.5,0.5")


def test_text_truncated():
    text = embed.embed_text({"title": "t", "body": "x" * 20000})
    assert len(text) == embed.MAX_EMBED_CHARS and text.startswith("t\n\n")


def test_provider_error_reports_status_without_url():
    class Boom(FakeEmbeddingClient):
        def _embed(self, texts):
            raise HttpError(500, "https://embed.example.test/?key=SECRETKEY")

    code, out = run_cli([], StubStore(sigs(1)), Boom())
    assert code == 1 and "HTTP 500" in out and "SECRETKEY" not in out


def test_missing_env_names_variable(monkeypatch):
    monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
    out = io.StringIO()
    code = embed.run([], store_factory=lambda: StubStore([]), out=out)
    assert code == 2 and "EMBEDDING_PROVIDER" in out.getvalue()


def test_store_requests(make_client):
    client, transport = make_client([ok(b"[]"), ok(b"[]"), HttpResponse(204, {}, b"")])
    store = SupabaseStore("https://proj.supabase.co", SECRET, client)
    store.fetch_signals_to_embed(10)
    store.fetch_signals_to_embed(10, pain_only=False)
    store.save_signal_embedding(3, "[1.0]", "fake/m")
    pain_q = urllib.parse.unquote(transport.requests[0].url)
    assert "signal_extractions!inner" in pain_q and "embedding=is.null" in pain_q
    assert "signal_extractions.is_b2b=is.true" in pain_q
    assert "signal_extractions" not in urllib.parse.unquote(transport.requests[1].url)
    patch = transport.requests[2]
    assert patch.method == "PATCH" and patch.url.endswith("/raw_signals?id=eq.3")
    assert json.loads(patch.body) == {"embedding": "[1.0]", "embedding_model": "fake/m"}
