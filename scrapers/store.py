"""Persist RawSignal batches into public.raw_signals via Supabase REST (PostgREST).

Uses SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY from the environment only; the key is
sent as a header and never logged. Inserts are idempotent: rows that already exist
for (source_platform, external_id) are left untouched (``resolution=ignore-duplicates``),
so ``processed_at`` and later LLM state are never clobbered by a re-ingest.
Raw usernames never reach this module — RawSignal only carries ``author_handle_hash``.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from scrapers import config
from scrapers.http_client import HttpClient, HttpError
from scrapers.models import RawSignal

log = logging.getLogger(__name__)

RAW_SIGNALS_TABLE = "raw_signals"
INGESTION_RUNS_TABLE = "ingestion_runs"
SIGNAL_EXTRACTIONS_TABLE = "signal_extractions"
CONFLICT_COLUMNS = "source_platform,external_id"
BATCH_SIZE = 200  # rows per POST; keeps payloads well under PostgREST limits


@dataclass
class StoreResult:
    received: int = 0
    inserted: int = 0
    skipped: int = 0

    def add(self, other: StoreResult) -> None:
        self.received += other.received
        self.inserted += other.inserted
        self.skipped += other.skipped


class SupabaseStore:
    def __init__(self, url: str, service_key: str, client: HttpClient | None = None) -> None:
        self._base = url.rstrip("/") + "/rest/v1"
        self._headers = {"apikey": service_key, "Authorization": f"Bearer {service_key}"}
        self.client = client or HttpClient()

    @classmethod
    def from_env(cls, client: HttpClient | None = None) -> SupabaseStore:
        return cls(
            config.require_env("SUPABASE_URL"),
            config.require_env("SUPABASE_SERVICE_ROLE_KEY"),
            client,
        )

    def _post(self, table: str, rows: list[dict[str, Any]], prefer: str,
              params: str = "") -> Any:
        resp = self.client.post_json(
            f"{self._base}/{table}{params}", rows, {**self._headers, "Prefer": prefer}
        )
        return resp.json() if resp.body else []

    def upsert_signals(self, signals: Iterable[RawSignal],
                       batch_size: int = BATCH_SIZE) -> StoreResult:
        """Insert new signals; duplicates (same platform + external_id) are skipped."""
        total = StoreResult()
        seen: set[tuple[str, str]] = set()
        batch: list[dict[str, Any]] = []
        for signal in signals:
            total.received += 1
            key = (signal.source_platform, signal.external_id)
            if key in seen:
                total.skipped += 1
                continue
            seen.add(key)
            batch.append(signal.to_row())
            if len(batch) >= batch_size:
                total.add(self._insert_batch(batch))
                batch = []
        if batch:
            total.add(self._insert_batch(batch))
        return total

    def _insert_batch(self, rows: list[dict[str, Any]]) -> StoreResult:
        returned = self._post(
            RAW_SIGNALS_TABLE,
            rows,
            "resolution=ignore-duplicates,return=representation",
            f"?on_conflict={CONFLICT_COLUMNS}&select=id",
        )
        inserted = len(returned) if isinstance(returned, list) else 0
        # received is counted by the caller; only report insert/skip split here
        return StoreResult(received=0, inserted=inserted, skipped=len(rows) - inserted)

    def table_exists(self, table: str) -> bool:
        try:
            self.client.get(f"{self._base}/{table}", {"select": "*", "limit": 0}, self._headers)
        except HttpError as exc:
            if exc.status in (404, 400):
                return False
            raise
        return True

    def record_run(self, row: Mapping[str, Any]) -> bool:
        """Best-effort ingestion_runs log; skipped when the table is absent or rejects it."""
        try:
            if not self.table_exists(INGESTION_RUNS_TABLE):
                log.info("%s not present; skipping run log", INGESTION_RUNS_TABLE)
                return False
            self._post(INGESTION_RUNS_TABLE, [dict(row)], "return=minimal")
        except HttpError as exc:
            # Status only: the exception text can contain a request URL.
            log.warning("could not write %s row: rejected with HTTP %s",
                        INGESTION_RUNS_TABLE, exc.status)
            return False
        return True

    # ---- generic helpers for the LLM pipeline (extract / embed) ----

    def select(self, table: str, params: Mapping[str, Any]) -> list[dict[str, Any]]:
        """GET rows with PostgREST query params (filters, select, order, limit)."""
        resp = self.client.get(f"{self._base}/{table}", params, self._headers)
        data = resp.json() if resp.body else []
        return data if isinstance(data, list) else []

    def patch(self, table: str, filters: Mapping[str, str], values: Mapping[str, Any]) -> None:
        query = "&".join(f"{k}={v}" for k, v in filters.items())
        self.client.patch_json(f"{self._base}/{table}?{query}", dict(values),
                               {**self._headers, "Prefer": "return=minimal"})

    def fetch_unprocessed_signals(self, limit: int) -> list[dict[str, Any]]:
        """raw_signals not yet extracted, oldest id first."""
        return self.select(RAW_SIGNALS_TABLE, {
            "select": "id,source_platform,title,body,tags",
            "processed_at": "is.null",
            "order": "id.asc",
            "limit": limit,
        })

    def save_extraction(self, row: Mapping[str, Any]) -> None:
        """Upsert one signal_extractions row (unique on signal_id)."""
        self._post(SIGNAL_EXTRACTIONS_TABLE, [dict(row)],
                   "resolution=merge-duplicates,return=minimal", "?on_conflict=signal_id")

    def mark_processed(self, signal_id: int, when: datetime) -> None:
        self.patch(RAW_SIGNALS_TABLE, {"id": f"eq.{int(signal_id)}"},
                   {"processed_at": when.isoformat()})

    def fetch_signals_to_embed(self, limit: int, *, pain_only: bool = True
                               ) -> list[dict[str, Any]]:
        """raw_signals with a null embedding; by default only B2B pain points."""
        params: dict[str, Any] = {
            "select": "id,title,body",
            "embedding": "is.null",
            "order": "id.asc",
            "limit": limit,
        }
        if pain_only:
            params["select"] = "id,title,body,signal_extractions!inner(is_pain_point,is_b2b)"
            params["signal_extractions.is_pain_point"] = "is.true"
            params["signal_extractions.is_b2b"] = "is.true"
        return self.select(RAW_SIGNALS_TABLE, params)

    def save_signal_embedding(self, signal_id: int, vector: str, model: str) -> None:
        self.patch(RAW_SIGNALS_TABLE, {"id": f"eq.{int(signal_id)}"},
                   {"embedding": vector, "embedding_model": model})
