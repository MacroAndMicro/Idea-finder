"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { fetchStats } from "@/lib/api";
import type { Stats } from "@/lib/types";
import { absFmt, relative } from "@/lib/time";

const num = new Intl.NumberFormat("en");

type State = { kind: "loading" } | { kind: "error" } | { kind: "ok"; stats: Stats; now: number };

/** Newest ingestion time we know of: latest run across sources, else newest fetched signal. */
function lastIngestion(s: Stats): string | null {
  const times = Object.values(s.last_runs ?? {})
    .map((r) => r?.last_run_at)
    .filter((t): t is string => !!t && !Number.isNaN(Date.parse(t)));
  if (times.length > 0) return times.reduce((a, b) => (Date.parse(a) >= Date.parse(b) ? a : b));
  const f = s.last_signal_fetched_at;
  return f && !Number.isNaN(Date.parse(f)) ? f : null;
}

function Figure({ label, value }: { label: string; value: number | undefined }) {
  return (
    <div className="flex flex-col gap-0.5 rounded border border-border bg-surface px-3 py-2 text-left">
      <dt className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</dt>
      <dd className="text-lg font-semibold tabular-nums">{value === undefined ? "—" : num.format(value)}</dd>
    </div>
  );
}

/**
 * IF-87: shown when the unfiltered card list is empty. Explains that the pipeline is working,
 * with live funnel counts from GET /api/stats. Every figure comes from the API; a missing one
 * shows "—". The stats call never blocks the list: on loading/error only the copy and link show.
 */
export default function PipelineEmptyState() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    const ctrl = new AbortController();
    fetchStats(ctrl.signal)
      .then((stats) => setState({ kind: "ok", stats, now: Date.now() }))
      .catch((e: Error) => {
        if (e.name !== "AbortError") setState({ kind: "error" });
      });
    return () => ctrl.abort();
  }, []);

  const s = state.kind === "ok" ? state.stats : null;
  const last = s ? lastIngestion(s) : null;
  const lastMs = last ? Date.parse(last) : NaN;

  return (
    <section
      aria-labelledby="empty-pipeline-heading"
      className="rounded-lg border border-dashed border-border p-6 text-center sm:p-8"
    >
      <h2 id="empty-pipeline-heading" className="font-medium">
        No opportunity cards yet
      </h2>
      <p className="mx-auto mt-1 max-w-prose text-sm text-muted">
        {s && s.total_signals > 0
          ? "The pipeline is collecting and analyzing real feedback. Cards appear here once analyzed signals are grouped into opportunities."
          : "Cards appear once signals are ingested from Reddit, GitHub, Hacker News and Stack Exchange, and analyzed."}
      </p>

      {state.kind === "loading" && <p className="mt-4 text-sm text-muted">Loading pipeline progress…</p>}
      {state.kind === "error" && (
        <p className="mt-4 text-sm text-muted">Pipeline progress is unavailable right now.</p>
      )}
      {s && (
        <dl className="mx-auto mt-5 grid max-w-2xl grid-cols-2 gap-3 sm:grid-cols-4">
          <Figure label="Signals collected" value={s.total_signals} />
          <Figure label="Signals analyzed" value={s.pipeline?.extracted_signals} />
          <Figure label="Pain points found" value={s.pipeline?.pain_points} />
          <div className="flex flex-col gap-0.5 rounded border border-border bg-surface px-3 py-2 text-left">
            <dt className="text-xs font-semibold uppercase tracking-wide text-muted">Last ingestion</dt>
            <dd className="text-sm font-semibold">
              {last && state.kind === "ok" ? (
                <time dateTime={last} title={`${absFmt.format(lastMs)} UTC`}>
                  {relative(lastMs, state.now)}
                </time>
              ) : (
                "Not yet"
              )}
            </dd>
          </div>
        </dl>
      )}

      <p className="mt-5">
        <Link
          href="/runs"
          className="inline-flex min-h-11 items-center rounded px-3 text-sm font-medium text-accent underline underline-offset-4 hover:no-underline"
        >
          See ingestion history
        </Link>
      </p>
    </section>
  );
}
