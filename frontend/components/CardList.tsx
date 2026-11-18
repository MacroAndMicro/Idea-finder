"use client";

import { useCallback, useEffect, useId, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { errorMessage, fetchCards, fetchFacets, queryFromParams, queryToParams, type CardQuery } from "@/lib/api";
import type { Facets, OpportunityCard, PageResponse } from "@/lib/types";
import OpportunityCardView from "./OpportunityCardView";
import PipelineEmptyState from "./PipelineEmptyState";
import SearchBox from "./SearchBox";

// min-w keeps selects from changing width when facet counts arrive.
const selectCls =
  "min-h-11 w-full min-w-44 rounded border border-border bg-surface px-2 text-sm text-foreground tabular-nums md:w-auto";

/** "Reddit (9)" once facets are in; just "Reddit" while loading or if facets failed. */
function withCount(label: string, n: number | undefined): string {
  return n === undefined ? label : `${label} (${n})`;
}

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

  // Facets: counts per filter option. Keyed by the filters (not page/sort) so
  // paging doesn't refetch; on error counts are simply left out.
  const facetQuery = useMemo(
    () => ({
      q: query.q,
      source: query.source,
      intent: query.intent,
      minConfidence: query.minConfidence,
      b2b: query.b2b,
      created: query.created,
    }),
    [query.q, query.source, query.intent, query.minConfidence, query.b2b, query.created],
  );
  // The previous counts stay visible while new ones load, so labels don't flicker.
  const [facets, setFacets] = useState<Facets | null>(null);
  useEffect(() => {
    const ctrl = new AbortController();
    fetchFacets(facetQuery, ctrl.signal)
      .then(setFacets)
      .catch((e: Error) => {
        if (e.name !== "AbortError") setFacets(null);
      });
    return () => ctrl.abort();
  }, [facetQuery]);
  const src = facets?.source_platform;
  const intent = facets?.economic_intent;

  const set = (patch: Partial<CardQuery>) => setQuery({ ...query, ...patch, page: 0 });

  // Below md the filters sit behind a disclosure so results start above the fold.
  const [filtersOpen, setFiltersOpen] = useState(false);
  const filtersId = useId();
  const activeFilters = [query.source, query.intent, query.minConfidence, query.b2b, query.created].filter(Boolean).length;
  // Reset clears every filter (not the search box or sort, which have their own controls).
  const resetFilters = () =>
    set({ source: undefined, intent: undefined, minConfidence: undefined, b2b: false, created: undefined });
  // "Filtered" = anything that narrows the list; an empty unfiltered list means no cards exist yet.
  const filtered = activeFilters > 0 || !!query.q;
  const sortChanged = query.sort !== "confidence";
  const onSearch = useCallback((q: string | undefined) => setQuery({ ...query, q, page: 0 }), [query, setQuery]);

  return (
    <div className="flex flex-col gap-6">
      <SearchBox value={query.q ?? ""} onSearch={onSearch} />
      <button
        type="button"
        aria-expanded={filtersOpen}
        aria-controls={filtersId}
        onClick={() => setFiltersOpen((o) => !o)}
        className="-mt-2 inline-flex min-h-11 items-center justify-between gap-2 self-start rounded border border-border bg-surface px-4 text-sm font-medium md:hidden"
      >
        <span>
          Filters &amp; sort
          {activeFilters > 0 && (
            <span className="ml-2 rounded-full bg-accent px-2 py-0.5 text-xs font-semibold text-accent-foreground tabular-nums">
              {activeFilters}
              <span className="sr-only"> active {activeFilters === 1 ? "filter" : "filters"}</span>
            </span>
          )}
          {sortChanged && <span className="ml-2 text-xs text-muted">· sorted</span>}
        </span>
        <span aria-hidden="true" className={`transition-transform ${filtersOpen ? "rotate-180" : ""}`}>
          ▾
        </span>
      </button>
      <form
        id={filtersId}
        className={`${filtersOpen ? "grid" : "hidden"} grid-cols-1 gap-4 min-[480px]:grid-cols-2 md:flex md:flex-wrap md:items-end`}
        aria-label="Filter opportunities"
        onSubmit={(e) => e.preventDefault()}
      >
        <label className="flex flex-col gap-1 text-sm font-medium">
          Source
          <select className={selectCls} value={query.source ?? ""} onChange={(e) => set({ source: e.target.value })}>
            <option value="">All sources</option>
            <option value="reddit">{withCount("Reddit", src?.reddit)}</option>
            <option value="github">{withCount("GitHub", src?.github)}</option>
            <option value="hackernews">{withCount("Hacker News", src?.hackernews)}</option>
            <option value="stackexchange">{withCount("Stack Exchange", src?.stackexchange)}</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium">
          Economic intent
          <select className={selectCls} value={query.intent ?? ""} onChange={(e) => set({ intent: e.target.value })}>
            <option value="">Any</option>
            <option value="High">{withCount("High", intent?.High)}</option>
            <option value="Medium">{withCount("Medium", intent?.Medium)}</option>
            <option value="Low">{withCount("Low", intent?.Low)}</option>
            <option value="Unspecified">{withCount("Unspecified", intent?.Unspecified)}</option>
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
          Added
          <select
            className={selectCls}
            value={query.created ?? ""}
            onChange={(e) => set({ created: (e.target.value || undefined) as CardQuery["created"] })}
          >
            <option value="">Any time</option>
            <option value="week">New this week (7 days)</option>
            <option value="month">New this month (30 days)</option>
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
          <span className="min-w-[4ch] tabular-nums text-muted">
            {facets?.is_b2b_filtered.true !== undefined ? `(${facets.is_b2b_filtered.true})` : ""}
          </span>
        </label>
        {activeFilters > 0 && (
          <button
            type="button"
            onClick={resetFilters}
            className="min-h-11 self-end rounded px-3 text-sm font-medium text-accent underline underline-offset-4 hover:no-underline"
          >
            Reset filters
          </button>
        )}
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
        {state.kind === "ok" && state.data.items.length === 0 && filtered && (
          <div className="rounded-lg border border-dashed border-border p-8 text-center">
            <p className="font-medium">
              {query.q ? (
                <>
                  No opportunities match “<span className="break-words">{query.q}</span>”
                </>
              ) : (
                "No opportunities match these filters"
              )}
            </p>
            <p className="mt-1 text-sm text-muted">
              {query.q ? "Try a shorter or different keyword, or loosen the filters." : "Try loosening the filters."}
            </p>
            <button
              type="button"
              onClick={() => setQuery({ sort: query.sort, page: 0 })}
              className="mt-3 min-h-11 rounded border border-border bg-surface px-4 text-sm font-medium"
            >
              {query.q ? "Clear search and filters" : "Clear filters"}
            </button>
          </div>
        )}
      </div>

      {state.kind === "ok" && state.data.items.length === 0 && !filtered && <PipelineEmptyState />}

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
