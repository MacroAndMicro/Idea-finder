"use client";

import { useEffect, useState } from "react";
import { errorMessage, fetchSignals } from "@/lib/api";
import type { Signal } from "@/lib/types";
import { safeHref, SourceBadge, When } from "./CardMeta";

type State = {
  items: Signal[];
  total: number;
  /** Next page to load, or null when every page is loaded. */
  next: number | null;
  status: "loading" | "idle" | "error";
  error?: string;
};

/** With a URL, the title link stretches over the whole item (44px+ touch target, IF-89). */
function SignalItem({ s }: { s: Signal }) {
  const title = s.title?.trim() || "Untitled post";
  const href = safeHref(s.url);
  return (
    <li className="relative flex flex-col gap-2 border-t border-border py-4 first:border-t-0 first:pt-0 last:pb-0">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
        <SourceBadge source={s.source_platform} />
        {s.source_created_at && <When iso={s.source_created_at} />}
        {s.score != null && (
          <span>
            <span className="font-semibold text-foreground tabular-nums">{s.score}</span> score
          </span>
        )}
        {s.comment_count != null && (
          <span>
            <span className="font-semibold text-foreground tabular-nums">{s.comment_count}</span>{" "}
            {s.comment_count === 1 ? "comment" : "comments"}
          </span>
        )}
      </div>
      <h3 className="text-sm font-semibold leading-snug">
        {href ? (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="stretched-link rounded text-accent underline-offset-4 hover:underline"
          >
            {title}
            <span className="sr-only"> (opens in new tab)</span>
          </a>
        ) : (
          title
        )}
      </h3>
      {s.body_snippet && <p className="line-clamp-4 text-sm text-muted break-words">{s.body_snippet}</p>}
    </li>
  );
}

/** Raw signals (evidence) behind a card, loaded page by page. */
export default function EvidenceList({ cardId }: { cardId: string }) {
  const [state, setState] = useState<State>({ items: [], total: 0, next: 0, status: "loading" });
  const [request, setRequest] = useState({ page: 0, attempt: 0 });

  useEffect(() => {
    const ctrl = new AbortController();
    fetchSignals(cardId, request.page, ctrl.signal)
      .then((data) =>
        setState((prev) => ({
          items: request.page === 0 ? data.items : [...prev.items, ...data.items],
          total: data.total_elements,
          next: data.page + 1 < data.total_pages ? data.page + 1 : null,
          status: "idle",
        })),
      )
      .catch((e: Error) => {
        if (e.name !== "AbortError") setState((prev) => ({ ...prev, status: "error", error: errorMessage(e) }));
      });
    return () => ctrl.abort();
  }, [cardId, request]);

  const load = (page: number) => {
    setState((prev) => ({ ...prev, status: "loading" }));
    setRequest((r) => ({ page, attempt: r.attempt + 1 }));
  };

  const firstLoad = state.items.length === 0;

  return (
    <section aria-labelledby="evidence-heading" className="flex flex-col gap-4 rounded-lg border border-border bg-surface p-4 sm:p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="evidence-heading" className="text-base font-semibold">
          Evidence
        </h2>
        {!firstLoad && (
          <p className="text-sm text-muted">
            Showing <span className="tabular-nums">{state.items.length}</span> of{" "}
            <span className="tabular-nums">{state.total}</span> {state.total === 1 ? "signal" : "signals"}
          </p>
        )}
      </div>

      {state.items.length > 0 && <ul className="flex flex-col">{state.items.map((s) => <SignalItem key={s.id} s={s} />)}</ul>}

      <div aria-live="polite">
        {state.status === "loading" && <p className="text-sm text-muted">Loading evidence…</p>}
        {state.status === "idle" && firstLoad && (
          <p className="text-sm text-muted">No source signals are linked to this card yet.</p>
        )}
        {state.status === "error" && (
          <div role="alert" className="rounded border border-danger p-3">
            <p className="text-sm font-medium text-danger">Couldn’t load evidence</p>
            <p className="mt-1 text-sm text-muted">{state.error}</p>
            <button
              type="button"
              onClick={() => load(state.next ?? 0)}
              className="mt-2 min-h-11 rounded bg-accent px-4 text-sm font-medium text-accent-foreground"
            >
              Try again
            </button>
          </div>
        )}
      </div>

      {state.status === "idle" && state.next != null && (
        <button
          type="button"
          onClick={() => load(state.next!)}
          className="min-h-11 self-start rounded border border-border px-4 text-sm font-medium"
        >
          Show more evidence
        </button>
      )}
    </section>
  );
}
