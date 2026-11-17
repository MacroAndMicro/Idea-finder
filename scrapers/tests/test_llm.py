import json

import pytest

from scrapers.config import MissingSecretError
from scrapers.llm import (
    EmbeddingDimensionError,
    ProviderNotSupportedError,
    embedding_client_from_env,
    llm_client_from_env,
)
from scrapers.llm.fake import FakeEmbeddingClient, FakeLLMClient
from scrapers.llm.gemini import GeminiEmbeddingClient, GeminiLLMClient
from scrapers.tests.helpers import ok


@pytest.fixture
def fake_env(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "fake")
    monkeypatch.setenv("EMBEDDING_DIMENSIONS", "1536")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)


def test_fake_providers_selected_by_env(fake_env):
    llm = llm_client_from_env()
    emb = embedding_client_from_env()
    assert isinstance(llm, FakeLLMClient) and isinstance(emb, FakeEmbeddingClient)
    assert emb.embedding_model == "fake/fake-embedding"


def test_fake_embeddings_deterministic_and_1536(fake_env):
    emb = embedding_client_from_env()
    a, b, c = emb.embed(["hello", "hello", "other"])
    assert len(a) == 1536 and a == b and a != c
    assert abs(sum(v * v for v in a) - 1.0) < 1e-9


def test_fake_llm_deterministic_json(fake_env):
    llm = llm_client_from_env()
    out = llm.complete("sys", "prompt", json_mode=True)
    assert json.loads(out) == json.loads(llm.complete("sys", "prompt", json_mode=True))


def test_wrong_configured_dimensions_raise(fake_env, monkeypatch):
    monkeypatch.setenv("EMBEDDING_DIMENSIONS", "768")
    with pytest.raises(EmbeddingDimensionError):
        embedding_client_from_env()


def test_wrong_returned_dimensions_raise():
    emb = FakeEmbeddingClient(output_dimensions=3072)
    with pytest.raises(EmbeddingDimensionError):
        emb.embed(["x"])


def test_unknown_provider_rejected(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "nope")
    monkeypatch.setenv("LLM_MODEL", "m")
    monkeypatch.setenv("LLM_API_KEY", "k")
    with pytest.raises(ProviderNotSupportedError):
        llm_client_from_env()


def test_missing_provider_vars_name_the_variable(monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "gemini")
    monkeypatch.setenv("EMBEDDING_DIMENSIONS", "1536")
    monkeypatch.setenv("EMBEDDING_MODEL", "m")
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)
    with pytest.raises(MissingSecretError, match="EMBEDDING_API_KEY"):
        embedding_client_from_env()


def test_gemini_embedding_request_shape_and_key_in_header(make_client):
    vec = [0.0] * 1536
    client, transport = make_client([ok({"embeddings": [{"values": vec}, {"values": vec}]})])
    emb = GeminiEmbeddingClient("embed-model", "KEY", client=client)
    assert emb.embed(["a", "b"]) == [vec, vec]
    req = transport.requests[0]
    assert req.method == "POST" and req.url.endswith("/embed-model:batchEmbedContents")
    assert "KEY" not in req.url and req.headers["x-goog-api-key"] == "KEY"
    body = json.loads(req.body)
    assert body["requests"][0]["outputDimensionality"] == 1536
    assert emb.embedding_model == "gemini/embed-model"


def test_gemini_embedding_wrong_size_rejected(make_client):
    client, _ = make_client([ok({"embeddings": [{"values": [0.1] * 768}]})])
    with pytest.raises(EmbeddingDimensionError):
        GeminiEmbeddingClient("m", "KEY", client=client).embed(["a"])


def test_gemini_llm_parses_text(make_client):
    reply = {"candidates": [{"content": {"parts": [{"text": '{"ok": '}, {"text": "true}"}]}}]}
    client, transport = make_client([ok(reply)])
    llm = GeminiLLMClient("llm-model", "KEY", client=client)
    assert json.loads(llm.complete("sys", "data", json_mode=True)) == {"ok": True}
    body = json.loads(transport.requests[0].body)
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert body["systemInstruction"]["parts"][0]["text"] == "sys"
