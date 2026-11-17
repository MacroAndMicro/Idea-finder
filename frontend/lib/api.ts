import type { OpportunityCard, PageResponse } from "./types";

const BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8080").replace(/\/$/, "");

export interface CardQuery {
  source?: string;
  intent?: string;
  minConfidence?: string;
  sort?: string;
  page?: number;
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
  params.set("page", String(q.page ?? 0));
  params.set("size", "12");
  const res = await fetch(`${BASE}/api/cards?${params}`, { signal });
  if (!res.ok) throw new Error(`The API responded with status ${res.status}.`);
  return res.json();
}
