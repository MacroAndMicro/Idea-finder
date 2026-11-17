"""Google Gemini over its public REST API (no SDK). Selected only via env vars."""

from __future__ import annotations

import urllib.parse

from scrapers.http_client import HttpClient
from scrapers.llm.base import EmbeddingClient, LLMClient

API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def _post(client: HttpClient, url: str, api_key: str, payload: dict) -> dict:
    # API key goes in a header, never in the URL (URLs can end up in logs).
    return client.post_json(url, payload, {"x-goog-api-key": api_key}).json()


def _model_path(model: str) -> str:
    return urllib.parse.quote(model.removeprefix("models/"), safe="-._")


class GeminiLLMClient(LLMClient):
    provider = "gemini"

    def __init__(self, model: str, api_key: str, client: HttpClient | None = None) -> None:
        super().__init__(model)
        self._key = api_key
        self._client = client or HttpClient(timeout=60.0)

    def complete(self, system: str, prompt: str, *, json_mode: bool = False) -> str:
        payload: dict = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2},
        }
        if json_mode:
            payload["generationConfig"]["responseMimeType"] = "application/json"
        data = _post(self._client, f"{API_BASE}/{_model_path(self.model)}:generateContent",
                     self._key, payload)
        candidates = data.get("candidates") or []
        if not candidates:
            raise RuntimeError("Gemini returned no candidates")
        parts = (candidates[0].get("content") or {}).get("parts") or []
        return "".join(p.get("text", "") for p in parts)


class GeminiEmbeddingClient(EmbeddingClient):
    provider = "gemini"

    def __init__(self, model: str, api_key: str, dimensions: int = 1536,
                 client: HttpClient | None = None) -> None:
        super().__init__(model, dimensions)
        self._key = api_key
        self._client = client or HttpClient(timeout=60.0)

    def _embed(self, texts: list[str]) -> list[list[float]]:
        model = _model_path(self.model)
        payload = {
            "requests": [
                {
                    "model": f"models/{model}",
                    "content": {"parts": [{"text": t}]},
                    "outputDimensionality": self.dimensions,
                }
                for t in texts
            ]
        }
        data = _post(self._client, f"{API_BASE}/{model}:batchEmbedContents", self._key, payload)
        return [list(e.get("values") or []) for e in data.get("embeddings") or []]
