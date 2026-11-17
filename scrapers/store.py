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
from typing import Any

from scrapers import config
from scrapers.http_client import HttpClient, HttpError
from scrapers.models import RawSignal

log = logging.getLogger(__name__)

RAW_SIGNALS_TABLE = "raw_signals"
INGESTION_RUNS_TABLE = "ingestion_runs"
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
