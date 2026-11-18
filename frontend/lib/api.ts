import type { Facets, IngestionRun, OpportunityCard, PageResponse, Signal, Stats } from "./types";

const BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8080").replace(/\/$/, "");

export interface CardQuery {
  /** Keyword search (title, problem statement, duct-tape solutions). */
  q?: string;
  source?: string;
  intent?: string;
  minConfidence?: string;
  sort?: string;
  b2b?: boolean;
  page?: number;
}

export const SORTS = ["confidence", "recent", "newest"] as const;

/** The API accepts q of 2–100 characters after trimming. */
export const Q_MIN = 2;
export const Q_MAX = 100;

/** Normalise a search term: trimmed, and dropped unless the API would accept it. */
export function cleanQ(raw: string | null | undefined): string | undefined {
  const t = (raw ?? "").trim().slice(0, Q_MAX);
  return t.length >= Q_MIN ? t : undefined;
}

/** Parse filter state from URL search params (unknown values are dropped). */
export function queryFromParams(p: URLSearchParams): CardQuery {
  const sort = p.get("sort") ?? "";
  const page = Number(p.get("page"));
  return {
    q: cleanQ(p.get("q")),
    source: p.get("source") ?? undefined,
    intent: p.get("intent") ?? undefined,
    minConfidence: p.get("minConfidence") ?? undefined,
    sort: (SORTS as readonly string[]).includes(sort) ? sort : "confidence",
    b2b: p.get("b2b") === "true",
    page: Number.isInteger(page) && page > 0 ? page : 0,
  };
}

/** Serialize filter state for the page URL (defaults omitted to keep URLs short). */
export function queryToParams(q: CardQuery): URLSearchParams {
  const p = new URLSearchParams();
  if (q.q) p.set("q", q.q);
  if (q.source) p.set("source", q.source);
  if (q.intent) p.set("intent", q.intent);
  if (q.minConfidence) p.set("minConfidence", q.minConfidence);
  if (q.sort && q.sort !== "confidence") p.set("sort", q.sort);
  if (q.b2b) p.set("b2b", "true");
  if (q.page) p.set("page", String(q.page));
  return p;
}

/** Filter params shared by /api/cards and /api/cards/facets. */
function filterParams(q: CardQuery): URLSearchParams {
  const params = new URLSearchParams();
  if (q.q) params.set("q", q.q);
  if (q.source) params.set("source", q.source);
  if (q.intent) params.set("intent", q.intent);
  if (q.minConfidence) params.set("minConfidence", q.minConfidence);
  if (q.b2b) params.set("b2b", "true");
  return params;
}

export async function fetchCards(
  q: CardQuery,
  signal?: AbortSignal,
): Promise<PageResponse<OpportunityCard>> {
  const params = filterParams(q);
  params.set("sort", q.sort || "confidence");
  params.set("page", String(q.page ?? 0));
  params.set("size", "12");
  return getJson(`/api/cards?${params}`, signal);
}

/** Error carrying the HTTP status, so callers can tell "not found" from other failures. */
export class ApiError extends Error {
  constructor(public status: number) {
    super(`The API responded with status ${status}.`);
    this.name = "ApiError";
  }
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { signal });
  if (!res.ok) throw new ApiError(res.status);
  return res.json();
}

/** Human-readable message for a failed request (network vs. API error). */
export function errorMessage(e: Error): string {
  return e instanceof TypeError ? "Could not reach the API. Check that the backend is running." : e.message;
}

export function fetchCard(id: string, signal?: AbortSignal): Promise<OpportunityCard> {
  return getJson(`/api/cards/${encodeURIComponent(id)}`, signal);
}

export const SIGNALS_PAGE_SIZE = 10;

export function fetchSignals(id: string, page: number, signal?: AbortSignal): Promise<PageResponse<Signal>> {
  return getJson(`/api/cards/${encodeURIComponent(id)}/signals?page=${page}&size=${SIGNALS_PAGE_SIZE}`, signal);
}

export function fetchStats(signal?: AbortSignal): Promise<Stats> {
  return getJson("/api/stats", signal);
}

/** Per-option counts for the current filters (same params as the list, no paging or sort). */
export function fetchFacets(q: CardQuery, signal?: AbortSignal): Promise<Facets> {
  const qs = filterParams(q).toString();
  return getJson(qs ? `/api/cards/facets?${qs}` : "/api/cards/facets", signal);
}

export const RUNS_PAGE_SIZE = 20;

export interface RunQuery {
  source?: string;
  status?: string;
  page?: number;
  size?: number;
}

/** Recent ingestion runs, newest first (GET /api/ingestion-runs). */
export function fetchRuns(q: RunQuery, signal?: AbortSignal): Promise<PageResponse<IngestionRun>> {
  const params = new URLSearchParams();
  if (q.source) params.set("source", q.source);
  if (q.status) params.set("status", q.status);
  params.set("page", String(q.page ?? 0));
  params.set("size", String(q.size ?? RUNS_PAGE_SIZE));
  return getJson(`/api/ingestion-runs?${params}`, signal);
}
