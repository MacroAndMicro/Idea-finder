import type { OpportunityCard, PageResponse } from "./types";

const BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8080").replace(/\/$/, "");

export interface CardQuery {
  source?: string;
  intent?: string;
  minConfidence?: string;
  sort?: string;
  b2b?: boolean;
  page?: number;
}

export const SORTS = ["confidence", "recent", "newest"] as const;

/** Parse filter state from URL search params (unknown values are dropped). */
export function queryFromParams(p: URLSearchParams): CardQuery {
  const sort = p.get("sort") ?? "";
  const page = Number(p.get("page"));
  return {
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
  if (q.source) p.set("source", q.source);
  if (q.intent) p.set("intent", q.intent);
  if (q.minConfidence) p.set("minConfidence", q.minConfidence);
  if (q.sort && q.sort !== "confidence") p.set("sort", q.sort);
  if (q.b2b) p.set("b2b", "true");
  if (q.page) p.set("page", String(q.page));
  return p;
}

export async function fetchCards(
  q: CardQuery,
  signal?: AbortSignal,
): Promise<PageResponse<OpportunityCard>> {
  const params = new URLSearchParams();
  if (q.source) params.set("source", q.source);
  if (q.intent) params.set("intent", q.intent);
  if (q.minConfidence) params.set("minConfidence", q.minConfidence);
  params.set("sort", q.sort || "confidence");
  if (q.b2b) params.set("b2b", "true");
  params.set("page", String(q.page ?? 0));
  params.set("size", "12");
  const res = await fetch(`${BASE}/api/cards?${params}`, { signal });
  if (!res.ok) throw new Error(`The API responded with status ${res.status}.`);
  return res.json();
}
