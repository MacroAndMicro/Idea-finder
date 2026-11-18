"""Google Gemini over its public REST API (no SDK). Selected only via env vars."""

from __future__ import annotations

import re
import urllib.parse

from scrapers.http_client import HttpClient, HttpResponse
from scrapers.llm.base import EmbeddingClient, LLMClient

API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

#: Generate calls: one retry only (each attempt can count against a small daily quota)
#: and give up on any server-requested wait above two minutes.
LLM_MAX_RETRIES = 1
LLM_MAX_WAIT_SECONDS = 120.0
#: Treated as "wait until tomorrow" when a 429 names a per-day quota without RetryInfo.
PER_DAY_WAIT_SECONDS = 86_400.0

_DELAY_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)s\s*$")


def gemini_retry_hint(resp: HttpResponse) -> float | None:
    """Seconds to wait from a Gemini error body (google.rpc.RetryInfo / QuotaFailure).

    Gemini sends no Retry-After header; a per-day quota 429 carries a ``retryDelay``
    of hours, which the HttpClient turns into QuotaExhausted instead of retrying.
    """
    if resp.status != 429:
        return None
    try:
        details = (resp.json().get("error") or {}).get("details") or []
    except (ValueError, AttributeError, UnicodeDecodeError):
        return None
    wait: float | None = None
    for item in details:
        if not isinstance(item, dict):
            continue
        match = _DELAY_RE.match(str(item.get("retryDelay") or ""))
        if match:
            wait = max(wait or 0.0, float(match.group(1)))
        violations = item.get("violations")
        for violation in violations if isinstance(violations, list) else []:
            if not isinstance(violation, dict):
                continue
            quota_id = str(violation.get("quotaId") or "")
            if "PerDay" in quota_id:
                wait = max(wait or 0.0, PER_DAY_WAIT_SECONDS)
    return wait


def _llm_http_client() -> HttpClient:
    return HttpClient(timeout=60.0, max_retries=LLM_MAX_RETRIES,
                      max_wait=LLM_MAX_WAIT_SECONDS, retry_hint=gemini_retry_hint)


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
        self._client = client or _llm_http_client()

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
        self._client = client or HttpClient(timeout=60.0, retry_hint=gemini_retry_hint)

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
