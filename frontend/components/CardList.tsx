"use client";

import { useEffect, useState } from "react";
import { fetchCards, type CardQuery } from "@/lib/api";
import type { OpportunityCard, PageResponse } from "@/lib/types";
import OpportunityCardView from "./OpportunityCardView";

const selectCls =
  "min-h-11 rounded border border-border bg-surface px-2 text-sm text-foreground";

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ok"; data: PageResponse<OpportunityCard> };

export default function CardList() {
  const [query, setQuery] = useState<CardQuery>({ sort: "confidence", page: 0 });
  const [result, setResult] = useState<{ key: string; state: State } | null>(null);
  const [attempt, setAttempt] = useState(0);
  const key = `${JSON.stringify(query)}#${attempt}`;
  const state: State = result?.key === key ? result.state : { kind: "loading" };

  useEffect(() => {
    const ctrl = new AbortController();
    fetchCards(query, ctrl.signal)
      .then((data) => setResult({ key, state: { kind: "ok", data } }))
      .catch((e: Error) => {
        if (e.name !== "AbortError") {
          const message = e instanceof TypeError ? "Could not reach the API. Check that the backend is running." : e.message;
          setResult({ key, state: { kind: "error", message } });
        }
      });
    return () => ctrl.abort();
  }, [query, key]);

  const set = (patch: Partial<CardQuery>) => setQuery((q) => ({ ...q, ...patch, page: 0 }));

  return (
    <div className="flex flex-col gap-6">
      <form className="flex flex-wrap items-end gap-4" aria-label="Filter opportunities" onSubmit={(e) => e.preventDefault()}>
        <label className="flex flex-col gap-1 text-sm font-medium">
          Source
          <select className={selectCls} value={query.source ?? ""} onChange={(e) => set({ source: e.target.value })}>
            <option value="">All sources</option>
            <option value="reddit">Reddit</option>
            <option value="github">GitHub</option>
            <option value="hackernews">Hacker News</option>
            <option value="stackexchange">Stack Exchange</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium">
          Economic intent
          <select className={selectCls} value={query.intent ?? ""} onChange={(e) => set({ intent: e.target.value })}>
            <option value="">Any</option>
            <option>High</option>
            <option>Medium</option>
            <option>Low</option>
            <option>Unspecified</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium">
          Min confidence
          <select className={selectCls} value={query.minConfidence ?? ""} onChange={(e) => set({ minConfidence: e.target.value })}>
            <option value="">Any</option>
            <option value="50">50+</option>
            <option value="70">70+</option>
            <option value="85">85+</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium">
          Sort by
          <select className={selectCls} value={query.sort} onChange={(e) => set({ sort: e.target.value })}>
            <option value="confidence">Confidence</option>
            <option value="newest">Newest</option>
          </select>
        </label>
      </form>

      <div aria-live="polite">
        {state.kind === "loading" && <p className="text-muted">Loading opportunities…</p>}
        {state.kind === "error" && (
          <div role="alert" className="rounded-lg border border-danger p-4">
            <p className="font-medium text-danger">Couldn’t load opportunities</p>
            <p className="mt-1 text-sm text-muted">{state.message}</p>
            <button
              type="button"
              onClick={() => setAttempt((a) => a + 1)}
              className="mt-3 min-h-11 rounded bg-accent px-4 text-sm font-medium text-accent-foreground"
            >
              Try again
            </button>
          </div>
        )}
        {state.kind === "ok" && state.data.items.length === 0 && (
          <div className="rounded-lg border border-dashed border-border p-8 text-center">
            <p className="font-medium">No opportunity cards yet</p>
            <p className="mt-1 text-sm text-muted">
              Cards appear once signals are ingested and extracted. Try loosening the filters.
            </p>
          </div>
        )}
      </div>

      {state.kind === "ok" && state.data.items.length > 0 && (
        <>
          <p className="text-sm text-muted">{state.data.total_elements} opportunities</p>
          <ul className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {state.data.items.map((c) => (
              <li key={c.id} className="flex">
                <div className="flex w-full"><OpportunityCardView card={c} /></div>
              </li>
            ))}
          </ul>
          <nav aria-label="Pagination" className="flex items-center justify-between gap-4">
            <button
              type="button"
              disabled={state.data.page <= 0}
              onClick={() => setQuery((q) => ({ ...q, page: (q.page ?? 0) - 1 }))}
              className="min-h-11 rounded border border-border px-4 text-sm disabled:opacity-50"
            >
              Previous
            </button>
            <span className="text-sm text-muted">
              Page {state.data.page + 1} of {Math.max(1, state.data.total_pages)}
            </span>
            <button
              type="button"
              disabled={state.data.page + 1 >= state.data.total_pages}
              onClick={() => setQuery((q) => ({ ...q, page: (q.page ?? 0) + 1 }))}
              className="min-h-11 rounded border border-border px-4 text-sm disabled:opacity-50"
            >
              Next
            </button>
          </nav>
        </>
      )}
    </div>
  );
}
