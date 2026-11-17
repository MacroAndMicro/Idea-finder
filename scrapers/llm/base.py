"""Interfaces every LLM / embedding provider implements."""

from __future__ import annotations

import abc
from collections.abc import Sequence

#: opportunity_cards.embedding is vector(1536); anything else is rejected.
REQUIRED_EMBEDDING_DIMENSIONS = 1536


class ProviderNotSupportedError(ValueError):
    pass


class EmbeddingDimensionError(ValueError):
    pass


class LLMClient(abc.ABC):
    provider: str

    def __init__(self, model: str) -> None:
        self.model = model

    @abc.abstractmethod
    def complete(self, system: str, prompt: str, *, json_mode: bool = False) -> str:
        """Return the model's text reply. ``prompt`` may contain untrusted data."""


class EmbeddingClient(abc.ABC):
    provider: str

    def __init__(self, model: str, dimensions: int = REQUIRED_EMBEDDING_DIMENSIONS) -> None:
        check_dimensions(dimensions)
        self.model = model
        self.dimensions = dimensions

    @property
    def embedding_model(self) -> str:
        """Value stored in opportunity_cards.embedding_model."""
        return f"{self.provider}/{self.model}"

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = self._embed(list(texts))
        if len(vectors) != len(texts):
            raise EmbeddingDimensionError(
                f"provider returned {len(vectors)} vectors for {len(texts)} texts"
            )
        for vec in vectors:
            check_dimensions(len(vec))
        return vectors

    @abc.abstractmethod
    def _embed(self, texts: list[str]) -> list[list[float]]: ...


def check_dimensions(n: int) -> None:
    if n != REQUIRED_EMBEDDING_DIMENSIONS:
        raise EmbeddingDimensionError(
            f"embedding dimension {n} != required {REQUIRED_EMBEDDING_DIMENSIONS}"
        )
