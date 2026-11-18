"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { errorMessage, fetchCards, queryFromParams, queryToParams, type CardQuery } from "@/lib/api";
import type { OpportunityCard, PageResponse } from "@/lib/types";
import OpportunityCardView from "./OpportunityCardView";
import SearchBox from "./SearchBox";

const selectCls =
  "min-h-11 rounded border border-border bg-surface px-2 text-sm text-foreground";

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ok"; data: PageResponse<OpportunityCard> };

export default function CardList() {
  // Filter state lives in the URL so views are shareable and survive reloads.
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const query = useMemo(() => queryFromParams(new URLSearchParams(params.toString())), [params]);
  const setQuery = useCallback(
    (next: CardQuery) => {
      const qs = queryToParams(next).toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [router, pathname],
  );
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
          setResult({ key, state: { kind: "error", message: errorMessage(e) } });
        }
      });
    return () => ctrl.abort();
  }, [query, key]);

  const set = (patch: Partial<CardQuery>) => setQuery({ ...query, ...patch, page: 0 });
  const onSearch = useCallback((q: string | undefined) => setQuery({ ...query, q, page: 0 }), [query, setQuery]);

  return (
    <div className="flex flex-col gap-6">
      <SearchBox value={query.q ?? ""} onSearch={onSearch} />
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
            <option value="recent">Most recent activity</option>
            <option value="newest">Newest card</option>
          </select>
        </label>
        <label className="flex min-h-11 cursor-pointer items-center gap-2 rounded border border-border bg-surface px-3 text-sm font-medium">
          <input
            type="checkbox"
            className="size-5 accent-accent"
            checked={query.b2b ?? false}
            onChange={(e) => set({ b2b: e.target.checked })}
          />
          B2B only
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
            {query.q ? (
              <>
                <p className="font-medium">
                  No opportunities match “<span className="break-words">{query.q}</span>”
                </p>
                <p className="mt-1 text-sm text-muted">Try a shorter or different keyword, or loosen the filters.</p>
              </>
            ) : (
              <>
                <p className="font-medium">No opportunity cards yet</p>
                <p className="mt-1 text-sm text-muted">
                  Cards appear once signals are ingested and extracted. Try loosening the filters.
                </p>
              </>
            )}
          </div>
        )}
      </div>

      {state.kind === "ok" && state.data.items.length > 0 && (
        <>
          <p className="text-sm text-muted">
            {state.data.total_elements} {state.data.total_elements === 1 ? "opportunity" : "opportunities"}
            {query.q && <> matching “<span className="break-words">{query.q}</span>”</>}
          </p>
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
              onClick={() => setQuery({ ...query, page: (query.page ?? 0) - 1 })}
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
              onClick={() => setQuery({ ...query, page: (query.page ?? 0) + 1 })}
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
