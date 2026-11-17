"""Select providers from LLM_* / EMBEDDING_* env vars. No vendor is hard-coded."""

from __future__ import annotations

from scrapers import config
from scrapers.llm.base import (
    EmbeddingClient,
    EmbeddingDimensionError,
    LLMClient,
    ProviderNotSupportedError,
    check_dimensions,
)
from scrapers.llm.fake import FakeEmbeddingClient, FakeLLMClient

SUPPORTED_PROVIDERS = ("fake", "gemini")


def llm_client_from_env() -> LLMClient:
    provider = config.require_env("LLM_PROVIDER").lower()
    if provider == "fake":
        return FakeLLMClient(config.get_env("LLM_MODEL", "fake-llm") or "fake-llm")
    model = config.require_env("LLM_MODEL")
    key = config.require_env("LLM_API_KEY")
    if provider == "gemini":
        from scrapers.llm.gemini import GeminiLLMClient

        return GeminiLLMClient(model, key)
    raise ProviderNotSupportedError(
        f"LLM_PROVIDER={provider!r} not supported (supported: {', '.join(SUPPORTED_PROVIDERS)})"
    )


def _dimensions_from_env() -> int:
    raw = config.require_env("EMBEDDING_DIMENSIONS")
    try:
        dims = int(raw)
    except ValueError as exc:
        raise EmbeddingDimensionError("EMBEDDING_DIMENSIONS must be an integer") from exc
    check_dimensions(dims)
    return dims


def embedding_client_from_env() -> EmbeddingClient:
    provider = config.require_env("EMBEDDING_PROVIDER").lower()
    dims = _dimensions_from_env()
    if provider == "fake":
        return FakeEmbeddingClient(
            config.get_env("EMBEDDING_MODEL", "fake-embedding") or "fake-embedding", dims
        )
    model = config.require_env("EMBEDDING_MODEL")
    key = config.require_env("EMBEDDING_API_KEY")
    if provider == "gemini":
        from scrapers.llm.gemini import GeminiEmbeddingClient

        return GeminiEmbeddingClient(model, key, dims)
    raise ProviderNotSupportedError(
        f"EMBEDDING_PROVIDER={provider!r} not supported "
        f"(supported: {', '.join(SUPPORTED_PROVIDERS)})"
    )
