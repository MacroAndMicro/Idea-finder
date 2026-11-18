"use client";

import { useEffect, useState } from "react";
import { fetchStats } from "@/lib/api";
import { SOURCE_LABELS, type SourcePlatform, type Stats } from "@/lib/types";

/** Phase 1 sources, always listed (0 when empty) so the strip keeps a stable shape. */
const SOURCES: SourcePlatform[] = ["reddit", "github", "hackernews", "stackexchange"];

const num = new Intl.NumberFormat("en");

type State = { kind: "loading" } | { kind: "error" } | { kind: "ok"; stats: Stats };

/**
 * How much evidence backs the product, per source. Purely informational: on error it renders
 * nothing so the card list still works.
 */
export default function StatsStrip() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    const ctrl = new AbortController();
    fetchStats(ctrl.signal)
      .then((stats) => setState({ kind: "ok", stats }))
      .catch((e: Error) => {
        if (e.name !== "AbortError") setState({ kind: "error" });
      });
    return () => ctrl.abort();
  }, []);

  if (state.kind === "error") return <div className="mb-6" />;
  if (state.kind === "loading") {
    // Reserves roughly the strip's height to avoid a layout jump when it loads.
    return <div className="mb-6 mt-4 min-h-16" aria-hidden="true" />;
  }

  const s = state.stats;
  if (s.total_signals === 0 && s.total_cards === 0) {
    return (
      <p className="mb-6 mt-4 text-sm text-muted">No signals ingested yet — evidence counts appear after the first ingestion run.</p>
    );
  }

  return (
    <section aria-label="Evidence coverage" className="mb-6 mt-4 rounded-lg border border-border bg-surface px-4 py-3">
      <dl className="flex flex-wrap gap-x-6 gap-y-3 text-sm">
        <div className="flex flex-col">
          <dt className="text-xs font-semibold uppercase tracking-wide text-muted">All sources</dt>
          <dd>
            <span className="font-semibold tabular-nums">{num.format(s.total_cards)}</span>{" "}
            {s.total_cards === 1 ? "card" : "cards"} ·{" "}
            <span className="font-semibold tabular-nums">{num.format(s.total_signals)}</span>{" "}
            {s.total_signals === 1 ? "signal" : "signals"}
          </dd>
        </div>
        {SOURCES.map((src) => {
          const cards = s.cards_by_source?.[src] ?? 0;
          const signals = s.signals_by_source?.[src] ?? 0;
          return (
            <div key={src} className="flex flex-col border-l border-border pl-6 max-sm:border-l-0 max-sm:pl-0">
              <dt className="text-xs font-semibold uppercase tracking-wide text-muted">{SOURCE_LABELS[src]}</dt>
              <dd className="text-muted">
                <span className="font-semibold text-foreground tabular-nums">{num.format(cards)}</span>{" "}
                {cards === 1 ? "card" : "cards"} ·{" "}
                <span className="font-semibold text-foreground tabular-nums">{num.format(signals)}</span>{" "}
                {signals === 1 ? "signal" : "signals"}
              </dd>
            </div>
          );
        })}
      </dl>
    </section>
  );
}
