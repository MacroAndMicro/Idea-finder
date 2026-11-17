"""Deterministic offline provider for tests and dry runs. Never calls a network."""

from __future__ import annotations

import hashlib
import json
import math
import struct

from scrapers.llm.base import EmbeddingClient, LLMClient


class FakeLLMClient(LLMClient):
    provider = "fake"

    def __init__(self, model: str = "fake-llm", responses: dict[str, str] | None = None) -> None:
        super().__init__(model)
        self.responses = responses or {}
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, prompt: str, *, json_mode: bool = False) -> str:
        self.calls.append((system, prompt))
        if prompt in self.responses:
            return self.responses[prompt]
        digest = hashlib.sha256(f"{system}\n{prompt}".encode()).hexdigest()[:16]
        return json.dumps({"echo": digest}) if json_mode else f"fake:{digest}"


class FakeEmbeddingClient(EmbeddingClient):
    provider = "fake"

    def __init__(self, model: str = "fake-embedding", dimensions: int = 1536,
                 output_dimensions: int | None = None) -> None:
        super().__init__(model, dimensions)
        # Lets tests simulate a misbehaving provider returning the wrong size.
        self._out = output_dimensions or dimensions

    def _embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def _vector(self, text: str) -> list[float]:
        raw: list[float] = []
        counter = 0
        while len(raw) < self._out:
            block = hashlib.sha256(f"{counter}:{text}".encode()).digest()
            raw.extend(v / 2**31 - 1.0 for v in struct.unpack(">8I", block))
            counter += 1
        raw = raw[: self._out]
        norm = math.sqrt(sum(v * v for v in raw)) or 1.0
        return [v / norm for v in raw]
