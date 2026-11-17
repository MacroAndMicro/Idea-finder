"""Provider-agnostic LLM and embedding clients (vendor chosen by env vars only)."""

from scrapers.llm.base import (
    REQUIRED_EMBEDDING_DIMENSIONS,
    EmbeddingClient,
    EmbeddingDimensionError,
    LLMClient,
    ProviderNotSupportedError,
)
from scrapers.llm.factory import embedding_client_from_env, llm_client_from_env

__all__ = [
    "REQUIRED_EMBEDDING_DIMENSIONS",
    "EmbeddingClient",
    "EmbeddingDimensionError",
    "LLMClient",
    "ProviderNotSupportedError",
    "embedding_client_from_env",
    "llm_client_from_env",
]
